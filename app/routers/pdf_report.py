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
from app.core.concurrency import limite_pesado
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
            "tipo_prenda": (of.tipo_prenda.value if hasattr(of.tipo_prenda, "value") else of.tipo_prenda) or "",
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
        with limite_pesado("Generando el reporte PDF"):
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


# ── Ficha de avance de una OF (PDF) ───────────────────────────
@router.get("/of/{of_id}/reporte-pdf")
def reporte_of_pdf(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    import datetime as _dt
    from app.services.gate_service import calcular_gates, gates_to_dict
    from app.services.corte_service import get_fases_strip
    from app.services import trazo_service
    from app.models.fase import OFFaseTiempos, OFFaseParada
    from app.constants import NOMBRES_FASE

    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    # ── Tiempos de corte de tela (F1–F3) + paradas ──────────────
    TELA = ["F1", "F2", "F3"]
    t_rows = {t.fase_id: t for t in db.query(OFFaseTiempos)
              .filter(OFFaseTiempos.of_id == of_id, OFFaseTiempos.fase_id.in_(TELA)).all()}
    fmt = lambda d: d.strftime("%d/%m %H:%M") if d else "—"
    inicios, fines, bruto = [], [], 0
    fases_tiempo = []
    for fid in TELA:
        t = t_rows.get(fid)
        ini = t.inicio_real if t else None
        fin = t.fin_real if t else None
        dur = int((fin - ini).total_seconds() // 60) if (ini and fin) else None
        if ini: inicios.append(ini)
        if fin: fines.append(fin)
        if dur: bruto += dur
        fases_tiempo.append({"nombre": NOMBRES_FASE.get(fid, fid),
                             "inicio": fmt(ini), "fin": fmt(fin), "dur": dur})
    span = int((max(fines) - min(inicios)).total_seconds() // 60) if (inicios and fines) else None
    paradas_rows = (db.query(OFFaseParada)
                    .filter(OFFaseParada.of_id == of_id, OFFaseParada.fase_id.in_(TELA))
                    .order_by(OFFaseParada.inicio_parada).all())
    paradas_total = sum((p.duracion_minutos or 0) for p in paradas_rows)
    tiempos = {
        "fases": fases_tiempo,
        "span": span, "bruto": bruto,
        "paradas_total": paradas_total,
        "efectivo": (bruto - paradas_total) if bruto else None,
        "lista_paradas": [
            {"fase": NOMBRES_FASE.get(p.fase_id, p.fase_id), "motivo": p.motivo,
             "dur": p.duracion_minutos, "fecha": fmt(p.inicio_parada)}
            for p in paradas_rows
        ],
    }

    prenda = of.prenda_catalogo
    gates = [] if of.es_muestra else gates_to_dict(calcular_gates(of, db))
    fases = get_fases_strip(of, db)

    # ── Numeración / Fusionado / Calidad / Reprocesos (derivados de paquetes) ──
    from app.services import paquete_service
    por_sku = paquete_service.resumen_calidad_por_talla(of_id, db)      # 1 sola vez
    res = paquete_service.resumen_calidad_of(of_id, db, porsku=por_sku)  # reutiliza

    # Corregir el avance de F4–F7 en "Avance por fase" con lo real (paquetes)
    if res["hay_hoja"]:
        _pct = {"F4": res["numeracion_pct"], "F5": res["fusionado_pct"],
                "F6": res["calidad_pct"],   "F7": res["liberado_pct"]}
        _done = {"F4": res["numeracion_done"], "F5": res["fusionado_done"],
                 "F6": res["calidad_done"],    "F7": res["liberado_done"]}
        for card in fases:
            fid = card["fase_id"]
            if fid in _pct:
                card["pct"] = _pct[fid]
                card["estado"] = ("completada" if _done[fid]
                                  else ("en_proceso" if _pct[fid] > 0 else "pendiente"))

    numeracion = fusionado = calidad = None
    reprocesos = []
    if res["hay_hoja"]:
        # meta por sku (nombre/orden/prendas) de la distribución — sin re-listar paquetes
        meta_sku = {d.sku_id: (d.sku.talla if d.sku else "—", d.sku.orden if d.sku else 0)
                    for d in of.talla_distribucion}
        prendas_sku = {d.sku_id: d.cantidad for d in of.talla_distribucion}
        tallas, total_paq, total_piezas = [], 0, 0
        for sku_id, r in por_sku.items():
            total_paq += r["paq_prenda"]
            total_piezas += r["num_paq"]
            talla, orden = meta_sku.get(sku_id, ("—", 0))
            tallas.append({
                "talla": talla, "paquetes": r["paq_prenda"], "piezas": r["num_paq"],
                "rango": ("{}–{}".format(r["num_min"], r["num_max"]) if r["num_min"] is not None else "—"),
                "prendas": prendas_sku.get(sku_id, r["total"]),
                "num_pct": r["numeracion_pct"], "fus_pct": r["fusionado_pct"],
                "cal_pct": r["calidad_pct"],
                "entregado": r["entregado"], "total": r["total"],
                "en_reproceso": r["en_reproceso"],
                "_orden": orden,
            })
        tallas.sort(key=lambda x: x["_orden"])

        t_f4 = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id="F4").first()
        f4i, f4f = (t_f4.inicio_real if t_f4 else None), (t_f4.fin_real if t_f4 else None)
        numeracion = {
            "inicio": fmt(f4i), "fin": fmt(f4f),
            "dur": (int((f4f - f4i).total_seconds() // 60) if (f4i and f4f) else None),
            "total_paquetes": total_paq, "total_piezas": total_piezas,
            "pct": res["numeracion_pct"], "tallas": tallas,
        }
        fusionado = {
            "inicio": fmt(res["fusionado_inicio"]), "fin": fmt(res["fusionado_fin"]),
            "pct": res["fusionado_pct"],
            "dur": (int((res["fusionado_fin"] - res["fusionado_inicio"]).total_seconds() // 60)
                    if (res["fusionado_inicio"] and res["fusionado_fin"]) else None),
        }
        calidad = {
            "entregado": res["entregado"], "total": res["total"],
            "en_reproceso": res["en_reproceso"], "pct": res["calidad_pct"], "tallas": tallas,
        }
        for r in paquete_service.listar_rechazos_of(of_id, db):
            p = r.paquete
            reprocesos.append({
                "pieza": p.pieza_nombre if p else "—",
                "talla": p.talla if p else "—",
                "bulto": p.numero if p else "—",
                "numeracion": ("{}–{}".format(p.numero_desde, p.numero_hasta) if p else "—"),
                "codigo": r.motivo.codigo if r.motivo else "—",
                "descripcion": r.motivo.descripcion if r.motivo else "",
                "cantidad": r.cantidad, "destino": r.destino or "—",
                "rehacer": "Sí" if r.rehacer else "No", "estado": r.estado,
            })

    distribucion = [
        {
            "talla": (d.sku.talla if d.sku else "—"),
            "codigo": (d.sku.codigo_sku if d.sku else None),
            "cantidad": d.cantidad,
        }
        for d in sorted(of.talla_distribucion, key=lambda x: (x.sku.orden if x.sku else 0))
    ]

    trazos = [
        {
            "nombre": t.nombre, "capas": t.capas,
            "capas_tendidas": t.capas_tendidas or 0, "capas_cortadas": t.capas_cortadas or 0,
            "metraje": t.metraje, "estado_tizado": t.estado_tizado,
            "estado_tendido": t.estado_tendido, "estado_corte": t.estado_corte,
            "total_prendas": t.total_prendas,
        }
        for t in trazo_service.listar_trazos(of_id, db)
    ]
    consumo = trazo_service.resumen_consumo(of_id, db)

    tmpl = templates.get_template("pdf/ficha_of.html")
    html_content = tmpl.render(
        of=of, prenda=prenda, gates=gates, fases=fases,
        distribucion=distribucion, trazos=trazos, consumo=consumo, tiempos=tiempos,
        numeracion=numeracion, fusionado=fusionado, calidad=calidad, reprocesos=reprocesos,
        total_dist=sum(d["cantidad"] for d in distribucion),
        hoy=_dt.date.today().strftime("%d/%m/%Y"),
        hora=_dt.datetime.now().strftime("%H:%M"),
        generado_por=current_user.nombre,
    )

    try:
        from xhtml2pdf import pisa
    except ImportError:
        raise HTTPException(500, "xhtml2pdf no instalado. Ejecuta: pip install xhtml2pdf")

    with limite_pesado("Generando la ficha PDF"):
        pdf_buffer = io.BytesIO()
        result = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        if result.err:
            logger.error("xhtml2pdf error ficha OF: %s", result.err)
            raise HTTPException(500, "Error al generar el PDF")
        pdf_buffer.seek(0)
    filename = "OF_{}_avance.pdf".format(of.numero_of)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=" + filename},
    )
