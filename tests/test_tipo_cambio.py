"""H6 · Tipo de cambio editable por día (parámetro del sistema).

Verifica que el TC de las hojas NUEVAS salga del parámetro editable por Logística,
con fallback al valor por defecto cuando no está cargado o es inválido.
"""
from app.routers.hoja_costos import tc_hoy, TC_HDC, TC_PARAM_KEY
from app.models.parametro import ParametroSistema


def test_tc_hoy_fallback_sin_parametro(db):
    # Sin valor cargado → usa el fallback por defecto
    assert tc_hoy(db) == TC_HDC


def test_tc_hoy_lee_valor_de_logistica(db):
    ParametroSistema.set(db, TC_PARAM_KEY, "3.812")
    assert tc_hoy(db) == 3.812


def test_tc_hoy_fallback_si_valor_invalido(db):
    ParametroSistema.set(db, TC_PARAM_KEY, "no-es-numero")
    assert tc_hoy(db) == TC_HDC
