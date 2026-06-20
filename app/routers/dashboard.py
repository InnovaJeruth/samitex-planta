from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload
from collections import defaultdict
import json

from app.database.connection import get_db
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.pieza import OFPieza
from app.models.usuario import Usuario
from app.services.semaforo_service import calcular_semaforo
from app.core.auth import get_current_user
from app.core.templates import templates

router = APIRouter()

FASES_DASH = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]
FASES_DASH_LBL = {
    "F1": "TZ", "F2": "TN", "F3": "CR",
    "F4": "NM", "F5": "FS", "F6": "HB", "F7": "H2",
}

SEM_RANK = {
    "VENCIDO": 0, "ALERTA": 1, "A_TIEMPO": 2,
    "OK_FECHA": 3, "OK_TARDE": 4, "SIN_FECHA": 5,
}
SEM_COLORES = {
    "VENCIDO":   "#c00000",
    "ALERTA":    "#bf9000",
    "A_TIEMPO":  "#0070c0",
    "OK_FECHA":  "#2e7d32",
    "OK_TARDE":  "#6b6b00",
    "SIN_FECHA": "#777777",
}


def _pct_of(of) -> int:
    """Calcula avance real de la OF basado en cantidad_actual / max_cantidad."""
    from app.models.of import EstadoOF
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


def _chips_pieza(pieza, of) -> dict:
    chips = {}
    for fid in FASES_DASH:
        if fid == "F5" and not pieza.fusionado:
            chips[fid] = {"estado": "na", "label": FASES_DASH_LBL[fid]}
            continue
        fe = next((f for f in pieza.fases_estado if f.fase_id == fid), None)
        if not fe:
            estado = "na"
        elif fe.completada:
            estado = "ok"
        elif fe.cantidad_actual > 0:
            estado = "par"
        else:
            estado = "pend"
        chips[fid] = {"estado": estado, "label": FASES_DASH_LBL[fid]}
    return chips


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    ofs_all = (
        db.query(OrdenFabricacion)
        .options(
            selectinload(OrdenFabricacion.piezas).selectinload(OFPieza.fases_estado)
        )
        .filter(OrdenFabricacion.estado != EstadoOF.ANULADA)
        .order_by(OrdenFabricacion.created_at.desc())
        .all()
    )

    kpis = {
        "total": 0, "borrador": 0, "activa": 0, "en_proceso": 0,
        "completada": 0, "vencidas": 0, "alertas": 0, "total_juegos": 0,
        "tercerizadas": 0,
    }

    clientes_raw = defaultdict(lambda: {
        "total_juegos": 0,
        "sem_rank": 99,
        "peor_sem": "SIN_FECHA",
        "sem_color": SEM_COLORES["SIN_FECHA"],
        "ofs": [],
    })

    prendas_prog = defaultdict(lambda: {"ok": 0, "total": 0})

    for of in ofs_all:
        sem = calcular_semaforo(of.fecha_apt, of.estado == EstadoOF.COMPLETADA)
        sem_estado = sem["estado"]

        kpis["total"]        += 1
        kpis["total_juegos"] += of.total_juegos
        if of.estado == EstadoOF.BORRADOR:     kpis["borrador"]   += 1
        elif of.estado == EstadoOF.ACTIVA:     kpis["activa"]     += 1
        elif of.estado == EstadoOF.EN_PROCESO: kpis["en_proceso"] += 1
        elif of.estado == EstadoOF.COMPLETADA: kpis["completada"] += 1
        if sem_estado == "VENCIDO": kpis["vencidas"] += 1
        elif sem_estado == "ALERTA": kpis["alertas"] += 1
        if getattr(of, "tercerizado", False): kpis["tercerizadas"] += 1

        tp = of.tipo_prenda.value
        for pieza in of.piezas:
            for fe in pieza.fases_estado:
                prendas_prog[tp]["total"] += 1
                if fe.completada:
                    prendas_prog[tp]["ok"] += 1

        pct = _pct_of(of)
        piezas_data = [
            {"pieza": p, "chips": _chips_pieza(p, of)}
            for p in of.piezas
        ]

        c = clientes_raw[of.cliente]
        c["total_juegos"] += of.total_juegos
        c["ofs"].append({
            "of": of, "sem": sem, "pct": pct,
            "piezas_data": piezas_data,
        })

        rank = SEM_RANK.get(sem_estado, 5)
        if rank < c["sem_rank"]:
            c["sem_rank"] = rank
            c["peor_sem"] = sem_estado
            c["sem_color"] = sem["color"]

    clientes_data = []
    for nombre, c in clientes_raw.items():
        avg_pct = round(
            sum(item["pct"] for item in c["ofs"]) / len(c["ofs"])
        ) if c["ofs"] else 0

        ofs_sorted = sorted(
            c["ofs"],
            key=lambda x: SEM_RANK.get(x["sem"]["estado"], 5)
        )

        clientes_data.append({
            "nombre": nombre,
            "total_juegos": c["total_juegos"],
            "total_ofs": len(c["ofs"]),
            "peor_sem": c["peor_sem"],
            "sem_color": c["sem_color"],
            "avg_pct": avg_pct,
            "ofs": ofs_sorted,
        })

    clientes_data.sort(key=lambda x: x["total_juegos"], reverse=True)

    tipos_orden = ["SACO", "PANTALON", "CAMISA", "OTRO"]
    tipos_presentes = [tp for tp in tipos_orden if tp in prendas_prog]
    PRENDA_COLORS = {"SACO": "#1a5ba3", "PANTALON": "#a36a0a", "CAMISA": "#1a6b35", "OTRO": "#3a3a6e"}

    clientes_detalle = {}
    for cli in clientes_data:
        prendas_agg = defaultdict(lambda: {
            "ok": 0, "total": 0,
            "piezas": defaultdict(lambda: {"ok": 0, "total": 0})
        })
        for item in cli["ofs"]:
            of = item["of"]
            tp = of.tipo_prenda.value
            for pieza in of.piezas:
                pname = pieza.nombre
                for fe in pieza.fases_estado:
                    prendas_agg[tp]["total"] += 1
                    prendas_agg[tp]["piezas"][pname]["total"] += 1
                    if fe.completada:
                        prendas_agg[tp]["ok"] += 1
                        prendas_agg[tp]["piezas"][pname]["ok"] += 1

        tipos_cli = list(prendas_agg.keys())
        clientes_detalle[cli["nombre"]] = {
            "prendas": {
                "labels": tipos_cli,
                "pct": [
                    round(prendas_agg[tp]["ok"] / prendas_agg[tp]["total"] * 100)
                    if prendas_agg[tp]["total"] else 0
                    for tp in tipos_cli
                ],
                "colors": [PRENDA_COLORS.get(tp, "#3a3a6e") for tp in tipos_cli],
            },
            "piezas": {
                tp: {
                    "labels": list(prendas_agg[tp]["piezas"].keys()),
                    "pct": [
                        round(prendas_agg[tp]["piezas"][pn]["ok"] /
                              prendas_agg[tp]["piezas"][pn]["total"] * 100)
                        if prendas_agg[tp]["piezas"][pn]["total"] else 0
                        for pn in prendas_agg[tp]["piezas"]
                    ],
                }
                for tp in tipos_cli
            }
        }

    chart_data = {
        "estados": {
            "labels": ["Borrador", "Activa", "En Proceso", "Completada"],
            "data":   [kpis["borrador"], kpis["activa"], kpis["en_proceso"], kpis["completada"]],
            "colors": ["#3a3a6e", "#1a5ba3", "#a36a0a", "#1a6b35"],
        },
        "clientes": {
            "labels":    [c["nombre"][:22] for c in clientes_data],
            "juegos":    [c["total_juegos"] for c in clientes_data],
            "ofs_count": [c["total_ofs"]    for c in clientes_data],
            "colors":    [c["sem_color"] + "cc" for c in clientes_data],
        },
        "prendas": {
            "labels": tipos_presentes,
            "pct": [
                round(prendas_prog[tp]["ok"] / prendas_prog[tp]["total"] * 100)
                if prendas_prog[tp]["total"] else 0
                for tp in tipos_presentes
            ],
            "colors": [PRENDA_COLORS.get(tp, "#3a3a6e") for tp in tipos_presentes],
        },
        "clientes_detalle": clientes_detalle,
    }

    return templates.TemplateResponse("dashboard/index.html", {
        "request":       request,
        "kpis":          kpis,
        "clientes_data": clientes_data,
        "chart_json":    json.dumps(chart_data),
        "current_user":  current_user,
        "FASES_DASH":    FASES_DASH,
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
            "id": of.id,
            "numero_of": of.numero_of,
            "cliente": of.cliente,
            "tipo_prenda": of.tipo_prenda,
            "total_juegos": of.total_juegos,
            "estado": of.estado,
      