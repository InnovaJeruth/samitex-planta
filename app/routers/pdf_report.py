"""
Router: Reporte PDF de estado de corte
Endpoint: GET /dashboard/reporte-pdf
"""
from __future__ import annotations

import io
import logging
import traceback
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.constants import ORDEN_FASES, NOMBRES_FASE
from app.core.auth import get_current_user
from app.core.templates import templates
from app.database.connection import get_db
from app.models.of import EstadoOF, OrdenFabricacion
from app.models.pieza import OFPieza
from app.models.usuario import Usuario
from app.services.semaforo_service import calcular_semaforo

router = APIRouter()
logger = logging.getLogger(__name__)


def _pct_of(of):
    if getattr(of, "tercerizado", False):
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


def _fases_sum(of):
    result = {}
    for fid in ORDEN_FASES:
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


def _fase_activa(fases):
    for fid in ORDEN_FASES:
        if fases.get(fid) in ("par", "pend"):
            return NOMBRES_FASE.get(fid, fid)
    return "Completada"


def _tiempos_fases(of):
    """Devuelve lista ordenada de tiempos por fase para el PDF."""
    orden_map = {fid: i for i, fid in enumerate(ORDEN_FASES)}
    filas = []
    for ft in (of.fase_tiempos or []):
        # desviacion en horas (fin_real vs fin_programado)
        dev = None
        if ft.fin_real and ft.fin_programado:
            dev = round((ft.fin_real - ft.fin_programado).total_seconds() / 3600, 1)

        # duracion real en horas
        dur_real = None
        if ft.inicio_real and ft.fin_real:
            dur_real = round((ft.fin_real - ft.inicio_real).total_seconds() / 3600, 1)

        filas.append({
            "fase_id":   ft.fase_id,
            "nombre":    NOMBRES_FASE.get(ft.fase_id, ft.fase_id),
            "ini_prog":  ft.inicio_programado.strftime("%d/%m %H:%M") if ft.inicio_programado else "-",
            "ini_real":  ft.inicio_real.strftime("%d/%m %H:%M")       if ft.inicio_real       else "-",
            "fin_prog":  ft.fin_programado.strftime("%d/%m %H:%M")    if ft.fin_programado    else "-",
            "fin_real":  ft.fin_real.strftime("%d/%m %H:%M")          if ft.fin_real          else "-",
            "dur_real":  dur_real,
            "dev":       dev,   # positivo = tarde, negativo = adelanto
        })
    filas.sort(key=lambda x: orden_map.get(x["fase_id"], 99))
    return filas


@router.get("/dashboard/reporte-pdf")
def reporte_pdf(
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
        .order_by(OrdenFabricacion.fecha_apt.asc())
        .all()
    )

    criticas    = []
    proximas    = []
    completadas = []
    activas     = []

    kpis = {
        "total": 0, "en_proceso": 0,
        "vencidas": 0, "alertas": 0,
        "completadas": 0, "juegos_activos": 0,
    }
    fase_pendiente = Counter()

    for of in ofs_all:
        sem     = calcular_semaforo(of.fecha_apt, of.estado == EstadoOF.COMPLETADA)
        sem_est = sem["estado"]
        pct     = _pct_of(of)
        fases   = _fases_sum(of)

        kpis["total"] += 1
        if of.estado == EstadoOF.COMPLETADA:
            kpis["completadas"] += 1
        if of.estado == EstadoOF.EN_PROCESO:
            kpis["en_proceso"] += 1
            kpis["juegos_activos"] += of.total_juegos or 0
        if sem_est == "VENCIDO":
            kpis["vencidas"] += 1
        elif sem_est == "ALERTA":
            kpis["alertas"] += 1

        if of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO):
            for fid, est in fases.items():
                if est in ("pend", "par"):
                    fase_pendiente[fid] += 1

        row = {
            "numero_of":   of.numero_of,
            "cliente":     of.cliente,
            "tipo_prenda": of.tipo_prenda.value if of.tipo_prenda else "",
            "juegos":      of.total_juegos or 0,
            "fecha_apt":   of.fecha_apt.strftime("%d/%m/%Y") if of.fecha_apt else "-",
            "dias":        sem["dias_restantes"],
            "pct":         pct,
            "sem_est":     sem_est,
            "estado":      of.estado.value,
            "fases":       fases,
            "fase_activa": _fase_activa(fases),
            "tiempos":     _tiempos_fases(of),
            "fecha_inicio": of.fecha_creacion.strftime("%d/%m/%Y") if of.fecha_creacion else "-",
        }

        if of.estado == EstadoOF.COMPLETADA:
            completadas.append(row)
        elif sem_est in ("VENCIDO", "ALERTA") and of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO):
            criticas.append(row)
        elif (
            of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO)
            and of.fecha_apt
            and of.fecha_apt >= hoy
            and of.fecha_apt <= hoy + timedelta(days=30)
        ):
            proximas.append(row)
            activas.append(row)
        elif of.estado in (EstadoOF.ACTIVA, EstadoOF.EN_PROCESO):
            activas.append(row)

    criticas.sort(key=lambda r: (0 if r["sem_est"] == "VENCIDO" else 1, r["fecha_apt"]))

    total_term = kpis["completadas"] + kpis["vencidas"]
    otd_rate   = round(kpis["completadas"] / total_term * 100) if total_term else None

    bottleneck = [
        {"fase": NOMBRES_FASE.get(fid, fid), "count": cnt}
        for fid, cnt in fase_pendiente.most_common(3)
    ]

    import datetime as _dt
    tmpl = templates.get_template("pdf/reporte_corte.html")
    html_content = tmpl.render(
        hoy=hoy.strftime("%d/%m/%Y"),
        hora=_dt.datetime.now().strftime("%H:%M"),
        generado_por=current_user.nombre,
        kpis=kpis,
        otd_rate=otd_rate,
        criticas=criticas,
        proximas=proximas,
        completadas=completadas,
        activas=activas,
        bottleneck=bottleneck,
        nombres_fase=NOMBRES_FASE,
        orden_fases=ORDEN_FASES,
    )

    try:
        from xhtml2pdf import pisa
    except ImportError:
        logger.error("xhtml2pdf no instalado")
        raise HTTPException(status_code=500, detail="xhtml2pdf no instalado. Ejecuta: pip install xhtml2pdf")

    try:
        pdf_buffer = io.BytesIO()
        result = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        if result.err:
            logger.error("xhtml2pdf error code: %s", result.err)
            raise HTTPException(status_code=500, detail="Error al generar el PDF")
        pdf_buffer.seek(0)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error generando PDF: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc))

    filename = "reporte_corte_{}.pdf".format(hoy.strftime("%Y%m%d"))
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=" + filename},
    )
