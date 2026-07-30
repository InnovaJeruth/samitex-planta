"""Process Mining · construcción del event log (solo lectura).

Modelo: **caso = bulto** (paquete). A cada bulto se le anteponen las fases de
tela de su OF (Tizado/Tendido/Corte, desde `of_fase_tiempos`), de modo que el
flujo arranca en **Tizado** y avanza bulto a bulto de forma correcta:

    Tizado → Tendido → Corte → Numerado → (Fusionado) → Enviado a calidad → Liberado

No depende de ninguna VIEW de BD (se calcula en Python) → testeable y portátil.
Cada evento: {case_id, of_id, activity, lifecycle, ts, resource_id, source},
ordenado por (case_id, ts).
"""
from collections import defaultdict
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.paquete import (
    OFPaquete, OFPaqueteEvento, OFReprocesoHito, OFPaqueteRechazo,
)
from app.models.fase import OFFaseTiempos
from app.constants import NOMBRES_FASE

# ── Taxonomía: estado del bulto → actividad canónica ────────────────────────
_ACT_ESTADO = {
    "HABILITADO":  "Numerado",
    "FUSIONADO":   "Enviado a fusionado",
    "POR_VALIDAR": "Enviado a calidad",
    "ENTREGADO":   "Liberado (OK calidad)",
    "STAND_BY":    "Rechazado (stand-by)",
}

# Fases de tela (nivel OF, comunes a todos los bultos de la OF)
_TELA_FASES = ["F1", "F2", "F3"]


def _act_reproceso(etapa: str) -> str:
    if etapa == "REINGRESADO":
        return "Reingreso a calidad"
    if etapa == "APROBADO":
        return "Aprobado (gerencia)"
    return "Reproceso: {}".format(etapa)


def _en_rango(ts, desde, hasta) -> bool:
    if ts is None:
        return False
    if desde and ts < desde:
        return False
    if hasta and ts > hasta:
        return False
    return True


def event_log(db: Session, of_ids: Optional[List[int]] = None,
              desde: Optional[datetime] = None, hasta: Optional[datetime] = None,
              incluir_tela: bool = True) -> List[dict]:
    """Event log (caso = bulto). Si `incluir_tela`, antepone Tizado/Tendido/Corte
    de la OF a cada bulto (flujo desde Tizado). `of_ids` filtra por una o varias OFs."""
    eventos: List[dict] = []

    # A) Transiciones de estado del bulto
    qa = (db.query(OFPaqueteEvento, OFPaquete.of_id)
            .join(OFPaquete, OFPaquete.id == OFPaqueteEvento.paquete_id))
    if of_ids:
        qa = qa.filter(OFPaquete.of_id.in_(of_ids))
    for e, ofid in qa.all():
        if not _en_rango(e.created_at, desde, hasta):
            continue
        eventos.append({
            "case_id": e.paquete_id, "of_id": ofid,
            "activity": _ACT_ESTADO.get(e.estado, e.estado),
            "lifecycle": "atomic", "ts": e.created_at,
            "resource_id": e.usuario_id, "source": "of_paquete_eventos",
        })

    # B) Fusionado: inicio y fin (nombres distintos → sin auto-bucle)
    qb = db.query(OFPaquete)
    if of_ids:
        qb = qb.filter(OFPaquete.of_id.in_(of_ids))
    for p in qb.all():
        if _en_rango(p.fusionado_inicio, desde, hasta):
            eventos.append({"case_id": p.id, "of_id": p.of_id, "activity": "Fusionado (inicio)",
                            "lifecycle": "start", "ts": p.fusionado_inicio,
                            "resource_id": None, "source": "of_paquetes.fusionado_inicio"})
        if _en_rango(p.fusionado_fin, desde, hasta):
            eventos.append({"case_id": p.id, "of_id": p.of_id, "activity": "Fusionado (fin)",
                            "lifecycle": "complete", "ts": p.fusionado_fin,
                            "resource_id": None, "source": "of_paquetes.fusionado_fin"})

    # C) Hitos de reproceso (enlazados al bulto vía el rechazo)
    qc = (db.query(OFReprocesoHito, OFPaquete.of_id, OFPaqueteRechazo.paquete_id)
            .join(OFPaqueteRechazo, OFPaqueteRechazo.id == OFReprocesoHito.rechazo_id)
            .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id))
    if of_ids:
        qc = qc.filter(OFPaquete.of_id.in_(of_ids))
    for h, ofid, paq_id in qc.all():
        if not _en_rango(h.at, desde, hasta):
            continue
        eventos.append({
            "case_id": paq_id, "of_id": ofid, "activity": _act_reproceso(h.etapa),
            "lifecycle": "atomic", "ts": h.at,
            "resource_id": h.usuario_id, "source": "of_reproceso_hitos",
        })

    # D) Anteponer fases de tela (Tizado/Tendido/Corte) de cada OF a sus bultos
    if incluir_tela:
        casos_of = {(ev["case_id"], ev["of_id"]) for ev in eventos}
        of_scope = {ofid for _, ofid in casos_of}
        tela = defaultdict(list)   # of_id → [(ts, activity, lifecycle)]
        if of_scope:
            qt = (db.query(OFFaseTiempos)
                    .filter(OFFaseTiempos.of_id.in_(of_scope),
                            OFFaseTiempos.fase_id.in_(_TELA_FASES)))
            for t in qt.all():
                nombre = NOMBRES_FASE.get(t.fase_id, t.fase_id)
                if t.inicio_real:
                    tela[t.of_id].append((t.inicio_real, "{} (inicio)".format(nombre), "start"))
                if t.fin_real:
                    tela[t.of_id].append((t.fin_real, "{} (fin)".format(nombre), "complete"))
        for lst in tela.values():
            lst.sort(key=lambda x: x[0])
        for case_id, ofid in casos_of:
            for ts, act, life in tela.get(ofid, []):
                if _en_rango(ts, desde, hasta):
                    eventos.append({"case_id": case_id, "of_id": ofid, "activity": act,
                                    "lifecycle": life, "ts": ts, "resource_id": None,
                                    "source": "of_fase_tiempos"})

    eventos.sort(key=lambda x: (x["case_id"], x["ts"]))
    return eventos


def event_log_bulto(db: Session, of_id: Optional[int] = None,
                    desde: Optional[datetime] = None,
                    hasta: Optional[datetime] = None) -> List[dict]:
    """Solo confección (desde Numerado), sin fases de tela. Compatibilidad."""
    return event_log(db, of_ids=[of_id] if of_id else None,
                     desde=desde, hasta=hasta, incluir_tela=False)


def build_event_log(db: Session, case_type: str = "OF",
                    of_ids: Optional[List[int]] = None,
                    desde: Optional[datetime] = None,
                    hasta: Optional[datetime] = None) -> List[dict]:
    """Dispatcher. `case_type='OF'` = flujo completo desde Tizado (con tela);
    `case_type='BULTO'` = solo confección desde Numerado."""
    return event_log(db, of_ids=of_ids, desde=desde, hasta=hasta,
                     incluir_tela=(case_type != "BULTO"))
