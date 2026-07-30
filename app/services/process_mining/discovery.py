"""Process Mining · descubrimiento de flujo (DFG) y variantes.

Sobre un event log ya ordenado por (case_id, ts) construye el grafo
directly-follows: nodos (actividad + frecuencia) y aristas (a→b con veces y
tiempo promedio en minutos).
"""
from collections import defaultdict
from typing import List


def _por_caso(eventos: List[dict]) -> dict:
    casos = defaultdict(list)
    for e in eventos:
        casos[e["case_id"]].append(e)
    # ya vienen ordenados globalmente por (case_id, ts); aseguramos por caso
    for evs in casos.values():
        evs.sort(key=lambda x: x["ts"])
    return casos


def dfg(eventos: List[dict]) -> dict:
    """Directly-Follows Graph. Devuelve {nodes, edges}.
    edge = {from, to, veces, min_prom}."""
    nodes = defaultdict(int)
    edges = defaultdict(lambda: {"veces": 0, "min_total": 0.0})

    casos = _por_caso(eventos)
    for e in eventos:
        nodes[e["activity"]] += 1

    for evs in casos.values():
        for a, b in zip(evs, evs[1:]):
            key = (a["activity"], b["activity"])
            mins = (b["ts"] - a["ts"]).total_seconds() / 60.0
            edges[key]["veces"] += 1
            edges[key]["min_total"] += mins

    nodes_out = [{"activity": k, "freq": v}
                 for k, v in sorted(nodes.items(), key=lambda kv: -kv[1])]
    edges_out = [{"from": a, "to": b, "veces": d["veces"],
                  "min_prom": round(d["min_total"] / d["veces"], 1) if d["veces"] else 0.0}
                 for (a, b), d in edges.items()]
    edges_out.sort(key=lambda x: -x["veces"])
    return {"nodes": nodes_out, "edges": edges_out}


def variantes(eventos: List[dict]) -> List[dict]:
    """Secuencias de actividades distintas y cuántos casos siguen cada una."""
    casos = _por_caso(eventos)
    conteo = defaultdict(int)
    for evs in casos.values():
        secuencia = tuple(e["activity"] for e in evs)
        conteo[secuencia] += 1
    out = [{"secuencia": list(s), "casos": n} for s, n in conteo.items()]
    out.sort(key=lambda x: -x["casos"])
    return out
