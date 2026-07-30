"""#2 · Ruta crítica por OF (CPM / longest-path sobre bultos en paralelo)."""
from datetime import datetime

from app.services.process_mining.critical_path import ruta_critica_of


def _e(case_id, activity, h, m, of_id=1):
    return {"case_id": case_id, "of_id": of_id, "activity": activity,
            "ts": datetime(2026, 7, 20, h, m)}


def test_elige_el_bulto_que_termina_ultimo():
    # Bulto 1 termina 09:30; bulto 2 termina 10:15 → crítico = 2
    evs = [
        _e(1, "Numerado", 8, 0), _e(1, "Liberado (OK calidad)", 9, 30),
        _e(2, "Numerado", 8, 0), _e(2, "Liberado (OK calidad)", 10, 15),
    ]
    r = ruta_critica_of(evs, of_id=1)
    assert r["bulto_critico"] == 2
    assert r["n_bultos"] == 2
    assert r["fin"] == datetime(2026, 7, 20, 10, 15)
    assert r["lead_time_min"] == 135.0            # 08:00 → 10:15
    assert r["dispersion_min"] == 45.0            # 09:30 vs 10:15


def test_paso_dominante_es_el_tramo_mas_largo():
    evs = [
        _e(5, "Tizado (inicio)", 6, 0),
        _e(5, "Numerado", 8, 0),                  # 120 min desde tizado (dominante)
        _e(5, "Fusionado (inicio)", 8, 20),       # 20 min
        _e(5, "Liberado (OK calidad)", 8, 35),    # 15 min
    ]
    r = ruta_critica_of(evs, of_id=1)
    assert r["paso_dominante"]["desde"] == "Tizado (inicio)"
    assert r["paso_dominante"]["hasta"] == "Numerado"
    assert r["paso_dominante"]["minutos"] == 120.0
    assert r["actividades"][0] == "Tizado (inicio)"
    assert len(r["pasos"]) == 3


def test_filtra_por_of():
    evs = [_e(1, "Numerado", 8, 0, of_id=1), _e(9, "Numerado", 8, 0, of_id=2)]
    r = ruta_critica_of(evs, of_id=2)
    assert r["bulto_critico"] == 9 and r["n_bultos"] == 1


def test_sin_eventos_devuelve_vacio():
    r = ruta_critica_of([], of_id=1)
    assert r["bulto_critico"] is None and r["lead_time_min"] == 0.0


def test_router_expone_ruta_critica():
    from app.routers import process_mining as pm
    paths = {r.path for r in pm.router.routes}
    assert "/api/ruta-critica/{of_id}" in paths


def test_integracion_con_event_log_real(db):
    # Reusa el setup del test de process mining para validar sobre datos de BD
    from tests.test_process_mining import _setup, _dt
    from app.models.fase import OFFaseTiempos
    from app.services.process_mining import event_log as el

    of, sku, pz, p1 = _setup(db)
    for fase, ini, fin in [("F1", _dt(6, 0), _dt(7, 0)), ("F2", _dt(7, 0), _dt(7, 30)),
                           ("F3", _dt(7, 30), _dt(7, 50))]:
        db.add(OFFaseTiempos(of_id=of.id, fase_id=fase, inicio_real=ini, fin_real=fin))
    db.commit()

    evs = el.build_event_log(db, of_ids=[of.id])
    r = ruta_critica_of(evs, of_id=of.id)
    assert r["bulto_critico"] == p1.id
    assert r["actividades"][0] == "Tizado (inicio)"        # arranca en tizado
    assert r["actividades"][-1] == "Liberado (OK calidad)"  # termina liberado
    assert r["lead_time_min"] > 0 and r["paso_dominante"] is not None
