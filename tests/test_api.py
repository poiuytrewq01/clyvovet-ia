import os

import pytest
from fastapi.testclient import TestClient

from app import database, ia
from app.main import app


@pytest.fixture(scope="module")
def client():
    database.inicializar(recriar=True)
    with TestClient(app) as c:
        yield c
    os.remove(database.DB_PATH)


def test_lista_pets(client):
    pets = client.get("/api/pets").json()
    assert len(pets) == 5
    assert {p["nome"]: p["urgencia"] for p in pets}["Luna"] == "ok"


def test_lembrete_usa_dados_do_pet(client):
    r = client.post("/api/pets/1/lembrete").json()
    assert r["urgencia"] == "media"
    assert "Rex" in r["mensagem"] and "Antirrábica" in r["mensagem"]
    assert "Labrador" in r["prompt"]  # o prompt leva o contexto do banco


def test_chat_emergencia_nao_chama_llm(client, monkeypatch):
    monkeypatch.setattr(ia, "gerar", lambda *a: pytest.fail("não devia chamar o LLM"))
    r = client.post("/api/pets/3/chat", json={"pergunta": "ele comeu veneno de rato"}).json()
    assert r["emergencia"] and r["origem"] == "regra"


def test_registrar_vacina_resolve_pendencia(client):
    antes = client.get("/api/pets/3/pendencias").json()
    vac_id = client.get("/api/pets/3").json()["vacinas"][0]["id"]
    client.delete(f"/api/pets/3/vacinas/{vac_id}")
    client.post("/api/pets/3/vacinas", json={"nome": "V10 - 2ª dose", "data_vencimento": "2027-09-29"})
    depois = client.get("/api/pets/3/pendencias").json()
    assert len(antes) == 1 and depois == []


def test_integracao_gemini_mockada(client, monkeypatch):
    """Simula a resposta HTTP do Gemini pra validar o caminho real da integração."""
    enviado = {}

    class Resp:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Oi! A antirrábica do Rex vence em 5 dias."}]}}]}

    def fake_post(url, headers, json, timeout):
        enviado.update(url=url, headers=headers, body=json)
        return Resp()

    monkeypatch.setenv("IA_MODO", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-teste")
    monkeypatch.setattr(ia.requests, "post", fake_post)
    r = client.post("/api/pets/1/lembrete").json()
    assert r["origem"] == "gemini"
    assert r["mensagem"].startswith("Oi!")
    assert enviado["headers"]["x-goog-api-key"] == "chave-teste"
    assert "Rex" in enviado["body"]["contents"][0]["parts"][0]["text"]


def test_falha_no_gemini_cai_no_simulado(client, monkeypatch):
    monkeypatch.setenv("IA_MODO", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-invalida")
    monkeypatch.setattr(ia.requests, "post", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("sem rede")))
    r = client.post("/api/pets/2/lembrete").json()
    assert r["origem"] == "simulado" and "Mia" in r["mensagem"]


def test_rotina_diaria_e_metricas(client):
    d = client.get("/api/lembretes/diario").json()
    assert d["total"] >= 3
    m = client.get("/api/metricas").json()
    assert m["total_mensagens"] > 0


def test_gemini_ocupado_tenta_de_novo(client, monkeypatch):
    chamadas = []

    class Resp:
        def __init__(self, code): self.status_code = code; self.text = "ocupado"
        def json(self): return {"candidates": [{"content": {"parts": [{"text": "Resposta após retry"}]}}]}

    def fake_post(*a, **k):
        chamadas.append(1)
        return Resp(503 if len(chamadas) < 3 else 200)

    monkeypatch.setenv("IA_MODO", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(ia.requests, "post", fake_post)
    monkeypatch.setattr(ia.time, "sleep", lambda s: None)
    r = client.post("/api/pets/1/lembrete").json()
    assert r["origem"] == "gemini" and len(chamadas) == 3
