"""Opción 3 · Animación de flujo (Celonis). Layout del grafo + tokens con tiempos."""
from datetime import datetime

from app.services.process_mining.animation import _layout, animacion


def test_layout_por_capas_izq_a_der():
    nodes = ["A", "B", "C"]
    edges = [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]
    pos = _layout(nodes, edges)
    assert pos["A"]["layer"] == 0 and pos["B"]["layer"] == 1 and pos["C"]["layer"] == 2
    assert pos["A"]["x"] < pos["B"]["x"] < pos["C"]["x"]   # avanza a la derecha


def test_layout_tolera_ciclos_de_reproceso():
    # A->B->C y back-edge C->B (reingreso): no debe colgar ni explotar capas
    nodes = ["A", "B", "C"]
    edges = [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "B"}]
    pos = _layout(nodes, edges)
    assert pos["C"]["layer"] >= pos["B"]["layer"]          # terminó, capas finitas


def test_animacion_con_datos_reales(db):
    from tests.test_process_mining import _setup, _dt
    from app.models.fase import OFFaseTiempos
    of, sku, pz, p1 = _setup(db)
    for fase, ini, fin in [("F1", _dt(6, 0), _dt(7, 0)), ("F2", _dt(7, 0), _dt(7, 30)),
                           ("F3", _dt(7, 30), _dt(7, 50))]:
        db.add(OFFaseTiempos(of_id=of.id, fase_id=fase, inicio_real=ini, fin_real=fin))
    db.commit()

    a = animacion(db, of_ids=[of.id])
    assert a["n_casos"] == 1
    assert a["nodes"] and a["edges"] and a["tokens"]
    # cada nodo tiene posición
    assert all("x" in n and "y" in n and "layer" in n for n in a["nodes"])
    # los tokens traen la secuencia con offset en segundos desde el inicio
    pasos = a["tokens"][0]["pasos"]
    assert pasos[0]["t"] == 0.0 and pasos[0]["activity"] == "Tizado (inicio)"
    assert a["dur_seg"] > 0 and a["width"] > 0 and a["height"] > 0


def test_animacion_vacia_sin_datos(db):
    a = animacion(db, of_ids=[99999])
    assert a["tokens"] == [] and a["nodes"] == []
