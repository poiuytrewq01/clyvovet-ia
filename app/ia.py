"""Serviço de IA Generativa do CLYVO VET.

Fluxo: dados do pet (banco) -> regras de urgência -> prompt -> LLM (Gemini) -> texto.
Sem chave de API, cai no modo "simulado" (templates), pra demo nunca quebrar.
"""
import os
import time

import requests
from dotenv import load_dotenv

from .urgencia import fase_de_vida, idade_texto, tutor_engajado

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

INSTRUCAO_SISTEMA = (
    "Você é a assistente virtual da CLYVO VET, uma clínica veterinária. "
    "Fale em português do Brasil, de forma acolhedora, clara e objetiva, sempre chamando o pet pelo nome. "
    "Use SOMENTE os dados do pet fornecidos; nunca invente vacinas, datas ou diagnósticos. "
    "Você não substitui o veterinário: não receite medicamentos nem doses. "
    "Diante de qualquer sintoma, oriente o tutor a agendar consulta na CLYVO VET."
)

TOM_POR_URGENCIA = {
    "urgente": "tom firme e direto, deixando claro que é importante agir hoje",
    "alta": "tom de alerta, mas gentil",
    "media": "tom amigável de lembrete",
    "baixa": "tom leve, só um aviso antecipado",
    "ok": "tom leve e positivo",
}


def modo_ia() -> str:
    if not os.getenv("CLYVO_TESTE"):
        load_dotenv(override=True)  # relê o .env a cada chamada: mudou a chave/modelo, não precisa reiniciar
    if os.getenv("IA_MODO", "").lower() == "simulado":
        return "simulado"
    return "gemini" if os.getenv("GEMINI_API_KEY") else "simulado"


def modelo() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


# ---------------------------------------------------------------- contexto

def montar_contexto(pet: dict, vacinas: list, consultas: list, medicamentos: list,
                    ultimo_checkin: str | None, pendencias: list) -> str:
    """Transforma os dados do banco num bloco de texto que o LLM entende."""
    fase = fase_de_vida(pet["especie"], pet["data_nascimento"])
    engajado, dias_sem = tutor_engajado(ultimo_checkin)
    linhas = [
        f"PET: {pet['nome']} | {pet['especie']} | raça {pet.get('raca') or 'não informada'} | "
        f"{idade_texto(pet['data_nascimento'])} ({fase}) | {pet.get('peso_kg') or '?'} kg",
        f"TUTOR: {pet.get('tutor_nome', 'tutor')}",
        "VACINAS: " + ("; ".join(f"{v['nome']} vence {v['data_vencimento']}" for v in vacinas) or "nenhuma registrada"),
        "CONSULTAS: " + ("; ".join(
            f"{c['data']} {c['motivo']}" + (f" (obs: {c['observacoes']})" if c.get("observacoes") else "")
            + (f" retorno previsto {c['retorno_em']}" if c.get("retorno_em") else "")
            for c in consultas) or "nenhuma registrada"),
        "MEDICAMENTOS: " + ("; ".join(
            f"{m['nome']} {m.get('dosagem') or ''} {m.get('frequencia') or ''} até {m.get('fim') or 'uso contínuo'}"
            for m in medicamentos) or "nenhum"),
        "ENGAJAMENTO DO TUTOR: " + (
            "sem check-ins registrados" if dias_sem is None
            else f"último check-in há {dias_sem} dias ({'ativo' if engajado else 'INATIVO'})"),
        "PENDÊNCIAS (já calculadas pelo sistema): " + ("; ".join(
            f"[{p['urgencia'].upper()}] {p['descricao']} " + _texto_dias(p) for p in pendencias) or "nenhuma"),
    ]
    return "\n".join(linhas)


def _texto_dias(p: dict) -> str:
    d = p["dias"]
    if d < 0:
        return f"(atrasada há {-d} dias)"
    if d == 0:
        return "(vence hoje)"
    return f"(vence em {d} dias)"


# ---------------------------------------------------------------- prompts

def prompt_lembrete(contexto: str, pendencia: dict | None, fase: str, engajado: bool) -> str:
    if pendencia is None:
        pedido = ("Não há pendências. Escreva uma mensagem curta (até 2 frases) parabenizando o tutor "
                  f"pelo cuidado e dando UMA dica de cuidado adequada a um pet {fase}.")
        tom = TOM_POR_URGENCIA["ok"]
    else:
        pedido = (f"Escreva um lembrete sobre a pendência principal: {pendencia['descricao']} "
                  f"{_texto_dias(pendencia)}. Relacione com a fase de vida do pet ({fase}) "
                  "e termine convidando a agendar na CLYVO VET.")
        tom = TOM_POR_URGENCIA[pendencia["urgencia"]]
    extra = "" if engajado else " O tutor está sumido do app: seja caloroso e convide-o a voltar a registrar os cuidados."
    return (f"{contexto}\n\nTAREFA: {pedido} Use {tom}.{extra} "
            "Máximo de 3 frases, sem emojis em excesso (no máximo 1), sem markdown.")


def prompt_chat(contexto: str, pergunta: str) -> str:
    return (f"{contexto}\n\nPERGUNTA DO TUTOR: {pergunta}\n\n"
            "Responda em até 5 frases, usando os dados acima quando fizer sentido. "
            "Se a pergunta for sobre sintoma ou doença, recomende consulta. Sem markdown.")


# ---------------------------------------------------------------- chamada ao LLM

def config_geracao(temperatura: float) -> dict:
    """Modelos 2.5 aceitam desligar o "raciocínio"; nos mais novos damos mais espaço de saída."""
    if modelo().startswith("gemini-2.5"):
        return {"temperature": temperatura, "maxOutputTokens": 1024, "thinkingConfig": {"thinkingBudget": 0}}
    return {"temperature": temperatura, "maxOutputTokens": 4096}


def chamar_gemini(prompt: str, temperatura: float = 0.7) -> str:
    corpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCAO_SISTEMA}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": config_geracao(temperatura),
    }
    # Google sobrecarregado (503) ou limite por minuto (429): espera e tenta de novo
    for tentativa in range(4):
        resp = requests.post(
            GEMINI_URL.format(modelo=modelo()),
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
            json=corpo,
            timeout=30,
        )
        if resp.status_code not in (429, 500, 503) or tentativa == 3:
            break
        print(f"[IA] Gemini ocupado (HTTP {resp.status_code}), tentando de novo...")
        time.sleep(2 * (tentativa + 1))
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
    dados = resp.json()
    try:
        return "".join(p.get("text", "") for p in dados["candidates"][0]["content"]["parts"]).strip()
    except (KeyError, IndexError):
        raise RuntimeError(f"Resposta sem texto: {str(dados)[:400]}")


ULTIMO_ERRO: str | None = None  # motivo da última falha do Gemini (mostrado na tela)


def gerar(prompt: str, fallback: str) -> tuple[str, str]:
    """Tenta o Gemini; se não houver chave ou der erro, usa o texto de fallback."""
    global ULTIMO_ERRO
    ULTIMO_ERRO = None
    if modo_ia() == "gemini":
        try:
            texto = chamar_gemini(prompt)
            if texto:
                return texto, "gemini"
            ULTIMO_ERRO = "O Gemini respondeu vazio."
        except Exception as e:  # rede, cota, chave inválida...
            ULTIMO_ERRO = f"{type(e).__name__}: {e}"
            print(f"[IA] Falha no Gemini, usando modo simulado: {ULTIMO_ERRO}")
    return fallback, "simulado"


# ---------------------------------------------------------------- fallbacks (modo simulado)

def lembrete_simulado(pet: dict, pendencia: dict | None, fase: str, engajado: bool) -> str:
    nome, especie = pet["nome"], pet["especie"]
    idade = idade_texto(pet["data_nascimento"])
    if pendencia is None:
        dica = {"filhote": "mantenha a socialização e o protocolo de vacinas em dia",
                "adulto": "um check-up anual ajuda a prevenir problemas",
                "idoso": "pets idosos se beneficiam de check-ups a cada 6 meses"}[fase]
        return f"Parabéns! {nome} está com tudo em dia. Dica para essa fase: {dica}."
    abertura = "" if engajado else "Sentimos sua falta por aqui! "
    d = pendencia["dias"]
    if pendencia["tipo"] == "vacina":
        oque = f"a vacina {pendencia['descricao']}"
    else:
        oque = f"o {pendencia['descricao'][0].lower()}{pendencia['descricao'][1:]}"
    situacao = (f"está atrasada há {-d} dias" if d < 0 else "vence hoje" if d == 0 else f"vence em {d} dias")
    if pendencia["tipo"] == "retorno" and d < 0:
        situacao = f"está atrasado há {-d} dias"
    base = f"{abertura}{nome} ({especie}, {idade}): {oque} {situacao}."
    if pendencia["urgencia"] == "urgente":
        return f"{base} Nessa fase de vida ({fase}), não vale a pena esperar: agende hoje com a CLYVO VET."
    if pendencia["urgencia"] == "alta":
        return f"{base} Agende o quanto antes com a CLYVO VET para manter {nome} protegido."
    return f"{base} Que tal já agendar com a CLYVO VET?"


def chat_simulado(pet: dict, pergunta: str, pendencias: list) -> str:
    p = pergunta.lower()
    nome = pet["nome"]
    if "vacina" in p or "pendên" in p or "pendenc" in p or "atras" in p:
        if not pendencias:
            return f"{nome} está com as vacinas e retornos em dia. Continue assim!"
        itens = "; ".join(f"{x['descricao']} {_texto_dias(x)}" for x in pendencias)
        return f"Pendências de {nome}: {itens}. Recomendo agendar com a CLYVO VET."
    return (f"(Modo simulado) Recebi sua pergunta sobre {nome}. Com a IA ativada, eu responderia usando "
            "o histórico completo do pet. Para qualquer sintoma, agende uma consulta na CLYVO VET.")
