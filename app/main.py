"""API do CLYVO VET (FastAPI). Rode com: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import ia  # noqa: E402
from .database import conectar, inicializar  # noqa: E402
from .urgencia import calcular_pendencias, detectar_emergencia, fase_de_vida, idade_texto, tutor_engajado  # noqa: E402

STATIC = Path(__file__).parent / "static"



@asynccontextmanager
async def lifespan(_app):
    inicializar()  # cria o banco com dados de exemplo na primeira execução
    yield


app = FastAPI(title="CLYVO VET - IA de cuidado contínuo", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ------------------------------------------------------------------ modelos de entrada

class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=2, max_length=500)


class VacinaIn(BaseModel):
    nome: str
    data_aplicacao: date | None = None
    data_vencimento: date


class CheckinIn(BaseModel):
    tipo: str = "passeio"


# ------------------------------------------------------------------ acesso a dados

def _lista(conn, sql, *args):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def carregar_pet(pet_id: int) -> dict:
    """Busca tudo que a IA precisa sobre o pet num único dicionário."""
    conn = conectar()
    pet = conn.execute(
        "SELECT p.*, t.nome AS tutor_nome FROM pets p JOIN tutores t ON t.id = p.tutor_id WHERE p.id = ?",
        (pet_id,),
    ).fetchone()
    if not pet:
        conn.close()
        raise HTTPException(404, "Pet não encontrado")
    dados = {
        "pet": dict(pet),
        "vacinas": _lista(conn, "SELECT * FROM vacinas WHERE pet_id = ? ORDER BY data_vencimento", pet_id),
        "consultas": _lista(conn, "SELECT * FROM consultas WHERE pet_id = ? ORDER BY data DESC", pet_id),
        "medicamentos": _lista(conn, "SELECT * FROM medicamentos WHERE pet_id = ?", pet_id),
        "checkins": _lista(conn, "SELECT * FROM checkins WHERE pet_id = ? ORDER BY data DESC LIMIT 10", pet_id),
    }
    conn.close()
    dados["ultimo_checkin"] = dados["checkins"][0]["data"] if dados["checkins"] else None
    dados["pendencias"] = calcular_pendencias(dados["vacinas"], dados["consultas"])
    return dados


def _contexto(d: dict) -> str:
    return ia.montar_contexto(d["pet"], d["vacinas"], d["consultas"], d["medicamentos"],
                              d["ultimo_checkin"], d["pendencias"])


def salvar_mensagem(pet_id, tipo, entrada, resposta, urgencia, origem):
    conn = conectar()
    conn.execute(
        "INSERT INTO mensagens_ia (pet_id, tipo, entrada, resposta, urgencia, origem) VALUES (?, ?, ?, ?, ?, ?)",
        (pet_id, tipo, entrada, resposta, urgencia, origem),
    )
    conn.commit()
    conn.close()


def gerar_lembrete(pet_id: int) -> dict:
    d = carregar_pet(pet_id)
    pet = d["pet"]
    fase = fase_de_vida(pet["especie"], pet["data_nascimento"])
    engajado, _ = tutor_engajado(d["ultimo_checkin"])
    principal = d["pendencias"][0] if d["pendencias"] else None
    prompt = ia.prompt_lembrete(_contexto(d), principal, fase, engajado)
    texto, origem = ia.gerar(prompt, ia.lembrete_simulado(pet, principal, fase, engajado))
    urg = principal["urgencia"] if principal else "ok"
    salvar_mensagem(pet_id, "lembrete", prompt, texto, urg, origem)
    return {"pet_id": pet_id, "pet": pet["nome"], "tutor": pet["tutor_nome"], "urgencia": urg,
            "pendencia": principal, "mensagem": texto, "origem": origem, "prompt": prompt,
            "erro_ia": ia.ULTIMO_ERRO}


# ------------------------------------------------------------------ rotas

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {"ia_modo": ia.modo_ia(), "modelo": ia.modelo() if ia.modo_ia() == "gemini" else None}


@app.get("/api/pets")
def listar_pets():
    conn = conectar()
    pets = _lista(conn, "SELECT p.*, t.nome AS tutor_nome FROM pets p JOIN tutores t ON t.id = p.tutor_id ORDER BY p.id")
    conn.close()
    saida = []
    for p in pets:
        pend = carregar_pet(p["id"])["pendencias"]
        saida.append({**p, "idade": idade_texto(p["data_nascimento"]),
                      "fase": fase_de_vida(p["especie"], p["data_nascimento"]),
                      "urgencia": pend[0]["urgencia"] if pend else "ok", "qtd_pendencias": len(pend)})
    return saida


@app.get("/api/pets/{pet_id}")
def detalhe_pet(pet_id: int):
    d = carregar_pet(pet_id)
    p = d["pet"]
    d["pet"] = {**p, "idade": idade_texto(p["data_nascimento"]), "fase": fase_de_vida(p["especie"], p["data_nascimento"])}
    engajado, dias = tutor_engajado(d["ultimo_checkin"])
    d["engajamento"] = {"ativo": engajado, "dias_sem_checkin": dias}
    return d


@app.get("/api/pets/{pet_id}/pendencias")
def pendencias(pet_id: int):
    return carregar_pet(pet_id)["pendencias"]


@app.post("/api/pets/{pet_id}/lembrete")
def lembrete(pet_id: int):
    return gerar_lembrete(pet_id)


@app.post("/api/pets/{pet_id}/chat")
def chat(pet_id: int, body: PerguntaIn):
    d = carregar_pet(pet_id)
    pet = d["pet"]
    # Regra de segurança: emergência não espera o LLM
    if detectar_emergencia(body.pergunta):
        texto = (f"⚠️ Isso pode ser uma emergência. Leve {pet['nome']} IMEDIATAMENTE a um pronto-atendimento "
                 "veterinário ou ligue para a CLYVO VET agora. Não dê medicamentos por conta própria.")
        salvar_mensagem(pet_id, "chat", body.pergunta, texto, "urgente", "regra")
        return {"resposta": texto, "origem": "regra", "emergencia": True}
    prompt = ia.prompt_chat(_contexto(d), body.pergunta)
    texto, origem = ia.gerar(prompt, ia.chat_simulado(pet, body.pergunta, d["pendencias"]))
    salvar_mensagem(pet_id, "chat", body.pergunta, texto, None, origem)
    return {"resposta": texto, "origem": origem, "emergencia": False, "erro_ia": ia.ULTIMO_ERRO}


@app.post("/api/pets/{pet_id}/vacinas", status_code=201)
def registrar_vacina(pet_id: int, v: VacinaIn):
    carregar_pet(pet_id)
    conn = conectar()
    conn.execute("INSERT INTO vacinas (pet_id, nome, data_aplicacao, data_vencimento) VALUES (?, ?, ?, ?)",
                 (pet_id, v.nome, v.data_aplicacao.isoformat() if v.data_aplicacao else None,
                  v.data_vencimento.isoformat()))
    conn.commit()
    conn.close()
    return {"ok": True, "pendencias": carregar_pet(pet_id)["pendencias"]}


@app.delete("/api/pets/{pet_id}/vacinas/{vacina_id}")
def remover_vacina(pet_id: int, vacina_id: int):
    """Usado quando a vacina é renovada: remove o registro antigo."""
    conn = conectar()
    conn.execute("DELETE FROM vacinas WHERE id = ? AND pet_id = ?", (vacina_id, pet_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/pets/{pet_id}/checkin", status_code=201)
def checkin(pet_id: int, c: CheckinIn):
    carregar_pet(pet_id)
    conn = conectar()
    conn.execute("INSERT INTO checkins (pet_id, data, tipo) VALUES (?, ?, ?)",
                 (pet_id, date.today().isoformat(), c.tipo))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/lembretes/diario")
def lembretes_diario():
    """Gera lembretes pra todos os pets com pendência. Chamado pelo fluxo do n8n."""
    conn = conectar()
    ids = [r[0] for r in conn.execute("SELECT id FROM pets ORDER BY id")]
    conn.close()
    saida = []
    for pid in ids:
        if carregar_pet(pid)["pendencias"]:
            r = gerar_lembrete(pid)
            r.pop("prompt")
            saida.append(r)
    return {"data": date.today().isoformat(), "total": len(saida), "lembretes": saida}


@app.get("/api/mensagens")
def historico_mensagens(limite: int = 50):
    conn = conectar()
    msgs = _lista(conn, "SELECT m.*, p.nome AS pet FROM mensagens_ia m JOIN pets p ON p.id = m.pet_id "
                        "ORDER BY m.id DESC LIMIT ?", limite)
    conn.close()
    return msgs


@app.get("/api/metricas")
def metricas():
    """Resultados para o relatório: quantas mensagens, por origem e urgência."""
    conn = conectar()
    por_origem = _lista(conn, "SELECT origem, COUNT(*) AS total FROM mensagens_ia GROUP BY origem")
    por_urg = _lista(conn, "SELECT urgencia, COUNT(*) AS total FROM mensagens_ia WHERE tipo='lembrete' GROUP BY urgencia")
    total = conn.execute("SELECT COUNT(*) FROM mensagens_ia").fetchone()[0]
    conn.close()
    return {"total_mensagens": total, "por_origem": por_origem, "lembretes_por_urgencia": por_urg}
