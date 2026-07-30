"""Process Mining · rendimiento: cuellos de botella y KPIs.

Sobre el event log calcula tiempos entre actividades consecutivas (para detectar
cuellos y esperas) y KPIs agregados del proceso.
"""
from collections import defaultdict
from typing import List

from app.services.process_mining.discovery import _por_caso

# Actividades que indican retrabajo (para el % de rework)
_REWORK = ("Rechazado (stand-by)", "Reingreso a calidad")


def cuellos(eventos: List[dict]) -> List[dict]:
    """Ranking de transiciones por tiempo promedio (min). Detecta dónde se
    pierde el tiempo. Cada fila: {from, to, casos, min_prom, min_max}."""
    agg = defaultdict(lambda: {"casos": 0, "total": 0.0, "max": 0.0})
    for evs in _por_caso(eventos).values():
        for a, b in zip(evs, evs[1:]):
            mins = (b["ts"] - a["ts"]).total_seconds() / 60.0
            k = (a["activity"], b["activity"])
            agg[k]["casos"] += 1
            agg[k]["total"] += mins
            agg[k]["max"] = max(agg[k]["max"], mins)
    out = [{"from": a, "to": b, "casos": d["casos"],
            "min_prom": round(d["total"] / d["casos"], 1) if d["casos"] else 0.0,
            "min_max": round(d["max"], 1)}
           for (a, b), d in agg.items()]
    out.sort(key=lambda x: -x["min_prom"])
    return out


def kpis(eventos: List[dict]) -> dict:
    """Resumen del proceso: nº de casos, lead time medio, % rework, top cuello."""
    casos = _por_caso(eventos)
    n_casos = len(casos)
    if not n_casos:
        return {"casos": 0, "lead_time_min_prom": 0.0, "pct_rework": 0.0, "top_cuello": None}

    lead_total = 0.0
    con_rework = 0
    for evs in casos.values():
        lead_total += (evs[-1]["ts"] - evs[0]["ts"]).total_seconds() / 60.0
        if any(e["activity"] in _REWORK for e in evs):
            con_rework += 1

    ranking = cuellos(eventos)
    top = ranking[0] if ranking else None
    return {
        "casos": n_casos,
        "lead_time_min_prom": round(lead_total / n_casos, 1),
        "pct_rework": round(con_rework / n_casos * 100, 1),
        "top_cuello": ({"transicion": "{} → {}".format(top["from"], top["to"]),
                        "min_prom": top["min_prom"]} if top else None),
    }
