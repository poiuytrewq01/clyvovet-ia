"""Regras de negócio que rodam ANTES do LLM.

A IA generativa só escreve o texto. Quem decide O QUE está pendente e QUÃO
urgente é são estas regras determinísticas (fáceis de testar e explicar).
"""
from datetime import date

# Ordem de prioridade (maior = mais urgente)
NIVEIS = {"ok": 0, "baixa": 1, "media": 2, "alta": 3, "urgente": 4}

PALAVRAS_EMERGENCIA = [
    "convuls", "não respira", "nao respira", "sangrando", "sangue", "envenen",
    "veneno", "atropelad", "desmaiou", "desmaio", "engasgad", "inconsciente",
    "chocolate", "não consegue andar", "nao consegue andar",
]


def _dt(valor: str) -> date:
    return date.fromisoformat(valor)


def idade_meses(data_nascimento: str, hoje: date | None = None) -> int:
    hoje = hoje or date.today()
    n = _dt(data_nascimento)
    return (hoje.year - n.year) * 12 + (hoje.month - n.month) - (1 if hoje.day < n.day else 0)


def fase_de_vida(especie: str, data_nascimento: str, hoje: date | None = None) -> str:
    meses = idade_meses(data_nascimento, hoje)
    if meses < 12:
        return "filhote"
    idoso_a_partir = 8 * 12 if especie == "cachorro" else 10 * 12
    return "idoso" if meses >= idoso_a_partir else "adulto"


def idade_texto(data_nascimento: str, hoje: date | None = None) -> str:
    meses = idade_meses(data_nascimento, hoje)
    if meses < 12:
        return f"{meses} {'mês' if meses == 1 else 'meses'}"
    anos = meses // 12
    return f"{anos} {'ano' if anos == 1 else 'anos'}"


def urgencia_vacina(data_vencimento: str, hoje: date | None = None) -> tuple[str, int]:
    """Retorna (nível, dias_para_vencer). Dias negativos = já vencida.

    - vencida há mais de 30 dias -> urgente
    - vencida (até 30 dias)      -> alta
    - vence em até 7 dias        -> media
    - vence em até 30 dias       -> baixa
    - mais de 30 dias            -> ok (não gera pendência)
    """
    hoje = hoje or date.today()
    dias = (_dt(data_vencimento) - hoje).days
    if dias < -30:
        return "urgente", dias
    if dias < 0:
        return "alta", dias
    if dias <= 7:
        return "media", dias
    if dias <= 30:
        return "baixa", dias
    return "ok", dias


def urgencia_retorno(retorno_em: str, hoje: date | None = None) -> tuple[str, int]:
    hoje = hoje or date.today()
    dias = (_dt(retorno_em) - hoje).days
    if dias < -30:
        return "urgente", dias
    if dias < 0:
        return "alta", dias
    if dias <= 7:
        return "media", dias
    return "ok", dias


def tutor_engajado(ultimo_checkin: str | None, hoje: date | None = None) -> tuple[bool, int | None]:
    """Tutor sem check-in há mais de 30 dias é considerado inativo."""
    if not ultimo_checkin:
        return False, None
    hoje = hoje or date.today()
    dias = (hoje - _dt(ultimo_checkin)).days
    return dias <= 30, dias


def calcular_pendencias(vacinas: list[dict], consultas: list[dict], hoje: date | None = None) -> list[dict]:
    """Lista de pendências do pet, da mais urgente para a menos urgente."""
    pend = []
    for v in vacinas:
        nivel, dias = urgencia_vacina(v["data_vencimento"], hoje)
        if nivel != "ok":
            pend.append({"tipo": "vacina", "descricao": v["nome"], "data": v["data_vencimento"],
                         "dias": dias, "urgencia": nivel})
    for c in consultas:
        if c.get("retorno_em") and not c.get("retorno_realizado"):
            nivel, dias = urgencia_retorno(c["retorno_em"], hoje)
            if nivel != "ok":
                pend.append({"tipo": "retorno", "descricao": f"Retorno da consulta ({c['motivo']})", "data": c["retorno_em"],
                             "dias": dias, "urgencia": nivel})
    pend.sort(key=lambda p: (-NIVEIS[p["urgencia"]], p["dias"]))
    return pend


def detectar_emergencia(texto: str) -> bool:
    t = texto.lower()
    return any(p in t for p in PALAVRAS_EMERGENCIA)
