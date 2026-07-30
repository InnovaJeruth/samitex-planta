"""Process Mining · Ruta crítica por OF (CPM / longest-path).

Innovación: aprovecha el PARALELISMO de bultos. Una OF corta muchos bultos que
avanzan a la vez y convergen al final; la OF termina cuando termina el ÚLTIMO
bulto. La ruta crítica es la cadena de actividades del bulto que determina ese
fin, con la duración de cada paso — así se ve qué tramo domina el lead time.

Formalmente: sobre un DAG con un nodo START (inicio de la OF), las cadenas de
cada bulto en paralelo y un nodo END que espera a todos, el **camino más largo**
START→END pasa por el bulto que termina último. Todo es lectura sobre el event
log ya construido (no toca datos ni esquema).
"""
from collections import defaultdict
from typing import List, Optional


def _min(a, b) -> float:
    return round((b - a).total_seconds() / 60.0, 1)


def ruta_critica_of(eventos: List[dict], of_id: Optional[int] = None) -> dict:
    """Ruta crítica de UNA OF a partir del event log (caso = bulto).

    `eventos` puede traer varias OFs; si se pasa `of_id`, se filtra a esa.
    Devuelve el bulto crítico, su secuencia de actividades, la duración de cada
    paso, el paso dominante (cuello) y el desfase entre el primer y último bulto
    en terminar (dispersión del paralelismo).
    """
    evs = [e for e in eventos if of_id is None or e.get("of_id") == of_id]
    vacio = {
        "of_id": of_id, "bulto_critico": None, "n_bultos": 0,
        "inicio": None, "fin": None, "lead_time_min": 0.0,
        "actividades": [], "pasos": [], "paso_dominante": None,
        "dispersion_min": 0.0,
    }
    if not evs:
        return vacio

    # 1) agrupar por bulto y ordenar cronológicamente
    por_bulto = defaultdict(list)
    for e in evs:
        por_bulto[e["case_id"]].append(e)
    for chain in por_bulto.values():
        chain.sort(key=lambda x: x["ts"])

    # 2) el bulto que termina ÚLTIMO es el crítico (define el fin de la OF)
    bulto_critico, cadena = max(por_bulto.items(), key=lambda kv: kv[1][-1]["ts"])
    inicio, fin = cadena[0]["ts"], cadena[-1]["ts"]

    # 3) duración de cada paso a lo largo de la ruta crítica
    pasos = [{"desde": a["activity"], "hasta": b["activity"], "minutos": _min(a["ts"], b["ts"])}
             for a, b in zip(cadena, cadena[1:])]
    paso_dominante = max(pasos, key=lambda p: p["minutos"]) if pasos else None

    # 4) dispersión del paralelismo: cuánto separa al primer del último bulto en terminar
    finales = [chain[-1]["ts"] for chain in por_bulto.values()]
    dispersion = _min(min(finales), max(finales))

    return {
        "of_id": of_id,
        "bulto_critico": bulto_critico,
        "n_bultos": len(por_bulto),
        "inicio": inicio, "fin": fin,
        "lead_time_min": _min(inicio, fin),
        "actividades": [e["activity"] for e in cadena],
        "pasos": pasos,
        "paso_dominante": paso_dominante,
        "dispersion_min": dispersion,
    }
