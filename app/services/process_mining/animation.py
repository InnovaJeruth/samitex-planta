"""Process Mining · datos para la animación de flujo estilo Celonis (solo lectura).

Devuelve el grafo con **posiciones** (layout por capas, izquierda→derecha) y los
**tokens** (cada caso = placa/paquete) con el tiempo real de cada paso normalizado
al inicio del proceso. El front mueve los tokens por las aristas a lo largo de un
reloj comprimido; los reprocesos aparecen como aristas hacia atrás (bucles).

Todo se calcula sobre el event log ya existente → no toca datos ni esquema.
"""
from collections import defaultdict
from typing import List, Optional

from sqlalchemy.orm import Session

from app.services.process_mining import event_log as el, discovery

_DX = 190   # separación horizontal entre capas
_DY = 95    # separación vertical dentro de una capa
_X0 = 40
_Y0 = 40


def _back_edges(nombres: List[str], pares: List[tuple]) -> set:
    """Back-edges (aristas de reproceso/ciclo) vía DFS: arista a un nodo 'gris'
    (en la pila de recursión). El grafo es pequeño → DFS recursivo es seguro."""
    adj = defaultdict(list)
    for u, v in pares:
        adj[u].append(v)
    color = defaultdict(int)   # 0 blanco, 1 gris (en pila), 2 negro
    back = set()

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 0:
                dfs(v)
            elif color[v] == 1:
                back.add((u, v))
        color[u] = 2

    for n in nombres:
        if color[n] == 0:
            dfs(n)
    return back


def _layout(nodes: List[str], edges: List[dict]) -> dict:
    """Layering por camino más largo (izq→der) sobre el DAG. Los back-edges
    (reprocesos) se excluyen del cálculo para no romper las capas."""
    pares = [(e["from"], e["to"]) for e in edges]
    back = _back_edges(nodes, pares)
    fwd = [(u, v) for (u, v) in pares if (u, v) not in back]

    layer = {n: 0 for n in nodes}
    for _ in range(len(nodes) + 1):
        cambio = False
        for u, v in fwd:
            if layer[v] < layer[u] + 1:
                layer[v] = layer[u] + 1
                cambio = True
        if not cambio:
            break

    por_capa = defaultdict(list)
    for n in nodes:
        por_capa[layer[n]].append(n)

    pos = {}
    for lay in sorted(por_capa):
        for i, n in enumerate(por_capa[lay]):
            pos[n] = {"x": _X0 + lay * _DX, "y": _Y0 + i * _DY, "layer": lay}
    return pos


def animacion(db: Session, of_ids: Optional[List[int]] = None) -> dict:
    """Grafo posicionado + tokens (casos) con tiempos reales para reproducir."""
    evs = el.build_event_log(db, of_ids=of_ids)
    vacio = {"nodes": [], "edges": [], "tokens": [],
             "t0": None, "t1": None, "dur_seg": 0.0, "width": 0, "height": 0}
    if not evs:
        return vacio

    g = discovery.dfg(evs)
    nombres = [n["activity"] for n in g["nodes"]]
    pos = _layout(nombres, g["edges"])

    nodes = [{"activity": n["activity"], "freq": n["freq"], **pos[n["activity"]]}
             for n in g["nodes"]]

    # aristas: marcar back-edge (rework) detectado por DFS
    back = _back_edges(nombres, [(e["from"], e["to"]) for e in g["edges"]])
    edges = [{**e, "back": (e["from"], e["to"]) in back} for e in g["edges"]]

    # tokens: cada caso con el offset (segundos) de cada paso desde el inicio
    t0 = min(e["ts"] for e in evs)
    t1 = max(e["ts"] for e in evs)
    por_caso = defaultdict(list)
    for e in evs:
        por_caso[e["case_id"]].append(e)

    tokens = []
    for cid, lst in por_caso.items():
        lst.sort(key=lambda x: x["ts"])
        pasos = [{"activity": e["activity"],
                  "t": round((e["ts"] - t0).total_seconds(), 1)} for e in lst]
        tokens.append({"case_id": cid, "pasos": pasos})

    width = max((p["x"] for p in pos.values()), default=0) + _DX
    height = max((p["y"] for p in pos.values()), default=0) + _DY
    return {
        "nodes": nodes, "edges": edges, "tokens": tokens,
        "t0": t0.isoformat(), "t1": t1.isoformat(),
        "dur_seg": round((t1 - t0).total_seconds(), 1),
        "width": width, "height": height, "n_casos": len(tokens),
    }
