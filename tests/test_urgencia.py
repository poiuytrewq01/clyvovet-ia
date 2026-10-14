from datetime import date

from app.urgencia import (calcular_pendencias, detectar_emergencia, fase_de_vida,
                          tutor_engajado, urgencia_vacina)

HOJE = date(2026, 9, 29)


def test_vacina_vencida_ha_mais_de_30_dias_e_urgente():
    assert urgencia_vacina("2026-08-15", HOJE) == ("urgente", -45)


def test_vacina_vencida_recente_e_alta():
    assert urgencia_vacina("2026-09-14", HOJE)[0] == "alta"


def test_vacina_vencendo_em_5_dias_e_media():
    assert urgencia_vacina("2026-10-04", HOJE) == ("media", 5)


def test_vacina_longe_de_vencer_nao_gera_pendencia():
    assert urgencia_vacina("2027-03-01", HOJE)[0] == "ok"


def test_fase_de_vida():
    assert fase_de_vida("cachorro", "2026-06-01", HOJE) == "filhote"
    assert fase_de_vida("cachorro", "2018-01-01", HOJE) == "idoso"
    assert fase_de_vida("gato", "2018-01-01", HOJE) == "adulto"  # gato só é idoso a partir de 10 anos


def test_tutor_inativo_depois_de_30_dias():
    assert tutor_engajado("2026-07-01", HOJE) == (False, 90)
    assert tutor_engajado("2026-09-25", HOJE)[0] is True


def test_pendencias_ordenadas_da_mais_urgente():
    vac = [{"nome": "V10", "data_vencimento": "2026-10-04"},
           {"nome": "Antirrábica", "data_vencimento": "2026-08-01"}]
    cons = [{"motivo": "Otite", "retorno_em": "2026-09-20", "retorno_realizado": 0}]
    pend = calcular_pendencias(vac, cons, HOJE)
    assert [p["urgencia"] for p in pend] == ["urgente", "alta", "media"]


def test_detecta_emergencia():
    assert detectar_emergencia("Meu cachorro comeu CHOCOLATE")
    assert not detectar_emergencia("qual a melhor ração?")
