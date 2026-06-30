from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import case
from collections import defaultdict, Counter
from datetime import date, timedelta, datetime as _dt
import json

from app.database.connection import get_db
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.pieza import OFPieza
from app.models.usuario import Usuario
from app.services.semaforo_service import calcular_semaforo
from app.core.auth import get_current_user
from app.core.templates import templates
from app.constants import ORDEN_FASES, NOMBRES_FASE

router = APIRouter()

SEM_RANK = {"VENCIDO": 0, "ALERTA": 1, "A_TIEMPO": 2, "OK_FECHA": 3, "OK_TARDE": 4, "SIN_FECHA": 5}
SEM_COLOR = {
    "VENCIDO": "#c0392b", "ALERTA": "#c87f0a",
    "A_TIEMPO": "#1a5ba3", "OK_FECHA": "#1e7d34",
    "OK_TARDE": "#6b6b00", "SIN_FECHA": "#555",
}

ESTADO_COLOR = {
    "BORRADOR": "#3a3a6e", "ACTIVA": "#1a5ba3",
    "EN_PROCESO": "#c87f0a", "COMPLETADA": "#1e7d34",
    "TERCERIZADA": "#7c3aed",
}

FASES_DASH = ["F1","F2","F3","F4","F8","F9","F5","F6","F7"]
FASES_DASH_LBL = {"F1":"Tizado","F2":"Tendido","F3":"Corte","F4":"Numerado",
                   "F8":"Estampado","F9":"Auditoría","F5":"Fusionado",
                   "F6":"Calidad","F7":"Habilitado"}


def _pct_of(of) -> int:
    if getattr(of, 'tercerizado', False):
        if of.estado == EstadoOF.COMPLETADA:
            return 100
        recibidos = sum(r.juegos_recibidos for r in of.recepciones_terc) if of.recepciones_terc else 0
        total_j = of.total_juegos or 0
        return min(round(recibidos / total_j * 100), 99) if total_j else 0
    cant_actual = sum(fe.cantidad_actual for p in of.piezas for fe in p.fases_estado)
    cant_max    = sum(fe.max_cantidad    for p in of.piezas for fe in p.fases_estado)
    if not cant_max:
        return 0
    pct = round(cant_actual / cant_max * 100)
    return 100 if of.estado == EstadoOF.COMPLETADA else min(pct, 99)


def _fases_sum(of) -> dict:
    """Resumen de estado por fase (agregado sobre todas las piezas)."""
    result = {}
    for fid in FASES_DASH:
        ok_c  = sum(1 for p in of.piezas for fe in p.fases_estado if fe.fase_id == fid and fe.completada)
        par_c = sum(1 for p in of.piezas for fe in p.fases_estado if fe.fase_id == fid and fe.cantidad_actual > 0 and not fe.completada)
        tot_c = sum(1 for p in of.piezas for fe in p.fases_estado if fe.fase_id == fid)
        if tot_c == 0:
            result[fid] = "na"
        elif ok_c == tot_c:
            result[fid] = "ok"
        elif ok_c > 0 or par_c > 0:
            result[fid] = "par"
        else:
            result[fid] = "pend"
    return result


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()

    ofs_all = (
        db.query(OrdenFabricacion)
        .options(
            selectinload(OrdenFabricacion.piezas).selectinload(OFPieza.fases_estado),
            selectinload(OrdenFabricacion.recepciones_terc),
            selectinload(OrdenFabricacion.fase_tiempos),
        )
        .filter(OrdenFabricacion.estado != EstadoOF.ANULADA)
        .order_by(
            case((OrdenFabricacion.fecha_apt == None, 1), else_=0),
            OrdenFabricacion.fecha_apt.asc(),
        )
        .all()
    )

    kpis = {"total": 0, "borrador": 0, "activa": 0, "en_proceso": 0,
            "completada": 0, "vencidas": 0, "alertas": 0, "total_juegos": 0}

    juegos_activos = 0
    fase_pendiente = Counter()      # bottleneck
    clientes_raw = defaultdict(lambda: {
        "total_juegos": 0, "sem_rank": 99,
        "peor_sem": "SIN_FECHA", "sem_color": SEM_COLOR["SIN_FECHA"],
        "rojo": 0, "naranja": 0, "verde": 0, "ofs": [],
    })

    for of in ofs_all:
        sem      = calcular_semaforo(of.fecha_apt, of.estado == EstadoOF.COMPLETADA)
        sem_est  = sem["estado"]
        pct      = _pct_of(of)
        fases_s  = _fases_sum(of)

        kpis["total"] += 1
        kpis["total_juegos"] += of.total_juegos or 0
        if of.estado == EstadoOF.BORRADOR:     kpis["borrador"]   += 1
        elif of.estado == EstadoOF.ACTIVA:     kpis["activa"]     += 1
        elif of.estado == EstadoOF.EN_PROCESO: kpis["en_proceso"] += 1
        elif of.estado == EstadoOF.COMPLETADA: kpis["completada"] += 1
        if sem_est == "VENCIDO": kpis["vencidas"] += 1
        elif sem_est == "ALERTA": kpis["alertas"]  += 1
        if of.estado == EstadoOF.EN_PROCESO:
            juegos_activos += of.total_juegos or 0

        # Bottleneck: OFs activas/en_proceso con fases pendientes
        if of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO):
            for fid, est in fases_s.items():
                if est in ("pend", "par"):
                    fase_pendiente[fid] += 1

        # Cascade data
        c = clientes_raw[of.cliente]
        c["total_juegos"] += of.total_juegos or 0
        if sem_est == "VENCIDO": c["rojo"]   += 1
        elif sem_est == "ALERTA": c["naranja"] += 1
        else: c["verde"] += 1

        rank = SEM_RANK.get(sem_est, 5)
        if rank < c["sem_rank"]:
            c["sem_rank"]  = rank
            c["peor_sem"]  = sem_est
            c["sem_color"] = SEM_COLOR[sem_est]

        # fases_prog para mini-Gantt en dashboard
        _now = _dt.now()
        fases_prog_dash = []
        for _t in of.fase_tiempos:
            if _t.inicio_real is not None:
                _ini = _t.inicio_real
                _fin = _t.fin_real if _t.fin_real else _now
                _tipo = "real_done" if _t.fin_real else "real_active"
            elif _t.inicio_programado is not None:
                _ini = _t.inicio_programado
                _fin = _t.fin_programado or (_t.inicio_programado + timedelta(hours=8))
                _tipo = "prog_late" if _fin.date() < hoy else "prog"
            else:
                continue
            fases_prog_dash.append({
                "fase_id": _t.fase_id,
                "nombre":  FASES_DASH_LBL.get(_t.fase_id, _t.fase_id),
                "inicio":  _ini.strftime("%Y-%m-%dT%H:%M"),
                "fin":     _fin.strftime("%Y-%m-%dT%H:%M"),
                "tipo":    _tipo,
            })

        c["ofs"].append({
            "id":        of.id,
            "numero_of": of.numero_of,
            "estado":    of.estado.value,
            "pct":       pct,
            "apt":       of.fecha_apt.isoformat() if of.fecha_apt else "",
            "apt_fmt":   of.fecha_apt.strftime("%d/%m/%Y") if of.fecha_apt else "—",
            "juegos":    of.total_juegos or 0,
            "sem_color": SEM_COLOR[sem_est],
            "sem_estado": sem_est,
            "fases":     fases_s,
            "fases_prog": fases_prog_dash,
        })

    # ── Métricas ejecutivas ────────────────────────────────────
    total_term = kpis["completada"] + kpis["vencidas"]
    otd_rate = round(kpis["completada"] / total_term * 100) if total_term else None

    proximas = [
        of for of in ofs_all
        if of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO)
        and of.fecha_apt and of.fecha_apt >= hoy
    ]
    proximo_apt = None
    if proximas:
        p = min(proximas, key=lambda x: x.fecha_apt)
        proximo_apt = {
            "numero_of": p.numero_of,
            "cliente":   p.cliente[:14],
            "fecha_apt": p.fecha_apt.strftime("%d/%m/%Y"),
            "dias":      (p.fecha_apt - hoy).days,
        }

    # ── Tendencia OTD últimas 4 semanas (proxy: fecha_apt) ────
    week_start = hoy - timedelta(days=hoy.weekday())
    otd_trend = []
    for i in range(3, -1, -1):
        ws = week_start - timedelta(weeks=i)
        we = ws + timedelta(days=6)
        w_ofs = [of for of in ofs_all if of.fecha_apt and ws <= of.fecha_apt <= we]
        w_comp = sum(1 for of in w_ofs if of.estado == EstadoOF.COMPLETADA)
        w_venc = sum(1 for of in w_ofs
                     if of.fecha_apt and of.fecha_apt < hoy
                     and of.estado != EstadoOF.COMPLETADA)
        w_total = w_comp + w_venc
        otd_trend.append({
            "label": "Esta sem" if i == 0 else f"S-{i}",
            "rate":  round(w_comp / w_total * 100) if w_total else None,
            "total": w_total,
        })

    # ── Velocidad: completadas esta semana vs anterior ────────
    comp_esta = sum(1 for of in ofs_all
                    if of.fecha_apt and of.fecha_apt >= week_start
                    and of.estado == EstadoOF.COMPLETADA)
    comp_ant  = sum(1 for of in ofs_all
                    if of.fecha_apt
                    and week_start - timedelta(weeks=1) <= of.fecha_apt < week_start
                    and of.estado == EstadoOF.COMPLETADA)

    metricas = {
        "otd_rate":       otd_rate,
        "juegos_activos": juegos_activos,
        "proximo_apt":    proximo_apt,
        "otd_trend":      otd_trend,
        "comp_esta_sem":  comp_esta,
        "comp_ant_sem":   comp_ant,
        "comp_delta":     comp_esta - comp_ant,
    }

    # ── Narrativa ─────────────────────────────────────────────
    narrativa = []
    vencidas_sin_inicio = [
        of for of in ofs_all
        if of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO)
        and of.fecha_apt and of.fecha_apt < hoy
    ]
    if vencidas_sin_inicio:
        n = len(vencidas_sin_inicio)
        narrativa.append({"tipo": "alerta", "msg": f"{n} OF{'s' if n > 1 else ''} vencida{'s' if n > 1 else ''} sin completar"})
    if kpis["alertas"] > 0:
        narrativa.append({"tipo": "warn", "msg": f"{kpis['alertas']} OF{'s' if kpis['alertas']>1 else ''} en alerta de plazo"})
    if otd_rate is not None and otd_rate >= 90:
        narrativa.append({"tipo": "ok", "msg": f"OTD {otd_rate}% — cumplimiento en meta"})
    elif otd_rate is not None:
        narrativa.append({"tipo": "warn", "msg": f"OTD {otd_rate}% — por debajo del objetivo"})
    if not narrativa:
        narrativa.append({"tipo": "ok", "msg": "Sin alertas activas"})

    # ── Cascade: build serializable list from clientes_raw ────────
    cascade_data = []
    for nombre, c in clientes_raw.items():
        cascade_data.append({
            "nombre":       nombre,
            "total_juegos": c["total_juegos"],
            "total_ofs":    len(c["ofs"]),
            "peor_sem":     c["peor_sem"],
            "sem_color":    c["sem_color"],
            "rojo":         c["rojo"],
            "naranja":      c["naranja"],
            "verde":        c["verde"],
            "ofs":          c["ofs"],
        })
    cascade_data.sort(key=lambda x: x["total_juegos"], reverse=True)

    # ── Bottleneck (server-side fallback, recalculated in JS) ─────
    bottleneck = [
        {"fid": fid, "label": FASES_DASH_LBL.get(fid, fid), "count": fase_pendiente[fid]}
        for fid in FASES_DASH if fase_pendiente[fid] > 0
    ]

    # ── Heatmap: completion % per fase across all OFs ─────────────
    heatmap = {}
    for fid in FASES_DASH:
        ok_c = sum(
            1 for of in ofs_all for p in of.piezas
            for fe in p.fases_estado if fe.fase_id == fid and fe.completada
        )
        tot_c = sum(
            1 for of in ofs_all for p in of.piezas
            for fe in p.fases_estado if fe.fase_id == fid
        )
        heatmap[fid] = round(ok_c / tot_c * 100) if tot_c else 0

    return templates.TemplateResponse("dashboard/index.html", {
        "request":          request,
        "kpis":             kpis,
        "metricas":         metricas,
        "cascade_json":     json.dumps(cascade_data),
        "narrativa_json":   json.dumps(narrativa),
        "bottleneck_json":  json.dumps(bottleneck),
        "heatmap_json":     json.dumps(heatmap),
        "fases_lbl_json":   json.dumps(FASES_DASH_LBL),
        "orden_fases_json": json.dumps(FASES_DASH),
        "estado_color_json": json.dumps(ESTADO_COLOR),
        "current_user":     current_user,
        "FASES_DASH":       FASES_DASH,
    })


@router.get("/api/ofs-resumen")
def ofs_resumen(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ofs = db.query(OrdenFabricacion).filter(
        OrdenFabricacion.estado != EstadoOF.ANULADA
    ).all()
    return [
        {
            "id":                of.id,
            "numero_of":         of.numero_of,
            "cliente":           of.cliente,
            "tipo_prenda":       of.tipo_prenda,
            "total_juegos":      of.total_juegos,
            "estado":            of.estado,
            "fecha_apt":         of.fecha_apt.isoformat() if of.fecha_apt else None,
            "fecha_inicio_plan": of.fecha_inicio_plan.isoformat() if of.fecha_inicio_plan else None,
        }
        for of in ofs
    ]
