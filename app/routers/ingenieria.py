"""
Router de Ingeniería Industrial — Samitex Planta
Endpoints para las 9 fichas de levantamiento de datos.
Prefijo: /ing
"""
import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.ingenieria import (
    IngSamRegistro,
    IngParadaRegistro,
    IngMuestreoObs,
    IngTendidoFicha,
    IngCalidadInspeccion,
    IngOleDiario,
    IngFusionadoParam,
    IngHabilitadoCierre,
    IngIshikawaCausa,
)

from app.models.of import OrdenFabricacion
from app.core.auth import get_current_user

# Auth a nivel de router: TODAS las rutas /ing exigen sesión iniciada.
router = APIRouter(prefix="/ing", tags=["Ingeniería"], dependencies=[Depends(get_current_user)])


def _resolve_of_id(db: Session, of_numero: str) -> Optional[int]:
    """Resuelve el id interno de la OF a partir de su número (clave de negocio).
    Devuelve None si la OF aún no está cargada — la ficha se guarda igual."""
    if not of_numero:
        return None
    of = db.query(OrdenFabricacion.id).filter(OrdenFabricacion.numero_of == of_numero).first()
    return of[0] if of else None


@router.get("/fichas", response_class=FileResponse)
def fichas_ingenieria():
    """Sirve la herramienta de fichas de levantamiento de ingeniería."""
    return FileResponse("static/fichas_ingenieria.html", media_type="text/html")


# ─────────────────────────────────────────────
# 1. SAM
# ─────────────────────────────────────────────
class SamIn(BaseModel):
    of_numero:         str
    fecha:             date
    operario:          str
    fase:              str
    elemento:          str
    tiempos:           list[float] = Field(default_factory=list)
    factor_valoracion: float = 100.0
    suplementos_pct:   float = 15.0
    tiempo_normal:     Optional[float] = None
    sam:               Optional[float] = None


@router.post("/sam", status_code=201)
def crear_sam(data: SamIn, db: Session = Depends(get_db)):
    rec = IngSamRegistro(
        of_numero=data.of_numero,
        of_id=_resolve_of_id(db, data.of_numero),
        fecha=data.fecha,
        operario=data.operario,
        fase=data.fase,
        elemento=data.elemento,
        tiempos_json=json.dumps(data.tiempos),
        factor_valoracion=data.factor_valoracion,
        suplementos_pct=data.suplementos_pct,
        tiempo_normal=data.tiempo_normal,
        sam=data.sam,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/sam")
def listar_sam(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngSamRegistro).order_by(IngSamRegistro.id.desc())
    if of_numero:
        q = q.filter(IngSamRegistro.of_numero == of_numero)
    rows = q.limit(limit).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id, "of_numero": r.of_numero, "fecha": str(r.fecha),
            "operario": r.operario, "fase": r.fase, "elemento": r.elemento,
            "tiempos": json.loads(r.tiempos_json) if r.tiempos_json else [],
            "factor_valoracion": r.factor_valoracion, "suplementos_pct": r.suplementos_pct,
            "tiempo_normal": r.tiempo_normal, "sam": r.sam,
        })
    return result


# ─────────────────────────────────────────────
# 2. Paradas
# ─────────────────────────────────────────────
class ParadaIn(BaseModel):
    of_numero:    str
    fecha:        date
    turno:        str
    fase:         str
    causa:        str
    duracion_min: float
    observacion:  Optional[str] = None


@router.post("/paradas", status_code=201)
def crear_parada(data: ParadaIn, db: Session = Depends(get_db)):
    rec = IngParadaRegistro(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/paradas")
def listar_paradas(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngParadaRegistro).order_by(IngParadaRegistro.id.desc())
    if of_numero:
        q = q.filter(IngParadaRegistro.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "of_numero": r.of_numero, "fecha": str(r.fecha),
         "turno": r.turno, "fase": r.fase, "causa": r.causa,
         "duracion_min": r.duracion_min, "observacion": r.observacion}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 3. Muestreo
# ─────────────────────────────────────────────
class MuestreoIn(BaseModel):
    of_numero:  str
    fecha:      date
    hora:       str
    fase:       str
    estado:     str
    observacion: Optional[str] = None


@router.post("/muestreo", status_code=201)
def crear_muestreo(data: MuestreoIn, db: Session = Depends(get_db)):
    rec = IngMuestreoObs(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/muestreo")
def listar_muestreo(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngMuestreoObs).order_by(IngMuestreoObs.id.desc())
    if of_numero:
        q = q.filter(IngMuestreoObs.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "of_numero": r.of_numero, "fecha": str(r.fecha),
         "hora": r.hora, "fase": r.fase, "estado": r.estado, "observacion": r.observacion}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 4. Tendido
# ─────────────────────────────────────────────
class TendidoIn(BaseModel):
    fecha:               date
    of_numero:           str
    tipo_prenda:         str
    tela_partida:        str
    largo_tender_m:      float
    num_capas:           int
    ancho_tela_m:        float
    num_prendas:         int
    retazo_kg:           float = 0.0
    area_tizado_m2:      float
    pct_aprovechamiento: Optional[float] = None
    area_tendida_m2:     Optional[float] = None


@router.post("/tendido", status_code=201)
def crear_tendido(data: TendidoIn, db: Session = Depends(get_db)):
    rec = IngTendidoFicha(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/tendido")
def listar_tendido(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngTendidoFicha).order_by(IngTendidoFicha.id.desc())
    if of_numero:
        q = q.filter(IngTendidoFicha.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "fecha": str(r.fecha), "of_numero": r.of_numero,
         "tipo_prenda": r.tipo_prenda, "tela_partida": r.tela_partida,
         "largo_tender_m": r.largo_tender_m, "num_capas": r.num_capas,
         "ancho_tela_m": r.ancho_tela_m, "num_prendas": r.num_prendas,
         "retazo_kg": r.retazo_kg, "area_tizado_m2": r.area_tizado_m2,
         "pct_aprovechamiento": r.pct_aprovechamiento, "area_tendida_m2": r.area_tendida_m2}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 5. Calidad
# ─────────────────────────────────────────────
class CalidadIn(BaseModel):
    fecha:               date
    of_numero:           str
    tipo_prenda:         str
    total_inspeccionado: int
    def_mal_corte:       int = 0
    def_fusionado:       int = 0
    def_numeracion:      int = 0
    def_tela:            int = 0
    def_medida:          int = 0
    def_otro:            int = 0
    total_defectos:      Optional[int] = None
    aprobadas:           Optional[int] = None
    fpy:                 Optional[float] = None


@router.post("/calidad", status_code=201)
def crear_calidad(data: CalidadIn, db: Session = Depends(get_db)):
    rec = IngCalidadInspeccion(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/calidad")
def listar_calidad(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngCalidadInspeccion).order_by(IngCalidadInspeccion.id.desc())
    if of_numero:
        q = q.filter(IngCalidadInspeccion.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "fecha": str(r.fecha), "of_numero": r.of_numero,
         "tipo_prenda": r.tipo_prenda, "total_inspeccionado": r.total_inspeccionado,
         "def_mal_corte": r.def_mal_corte, "def_fusionado": r.def_fusionado,
         "def_numeracion": r.def_numeracion, "def_tela": r.def_tela,
         "def_medida": r.def_medida, "def_otro": r.def_otro,
         "total_defectos": r.total_defectos, "aprobadas": r.aprobadas, "fpy": r.fpy}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 6. OLE
# ─────────────────────────────────────────────
class OleIn(BaseModel):
    of_numero:         str
    fecha:             date
    turno:             str
    fase:              str
    num_operarios:     int
    horas_programadas: float
    horas_trabajadas:  float
    produccion_real:   int
    produccion_std:    int
    piezas_buenas:     int
    disponibilidad:    Optional[float] = None
    rendimiento:       Optional[float] = None
    calidad_pct:       Optional[float] = None
    ole:               Optional[float] = None


@router.post("/ole", status_code=201)
def crear_ole(data: OleIn, db: Session = Depends(get_db)):
    rec = IngOleDiario(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/ole")
def listar_ole(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngOleDiario).order_by(IngOleDiario.id.desc())
    if of_numero:
        q = q.filter(IngOleDiario.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "of_numero": r.of_numero, "fecha": str(r.fecha),
         "turno": r.turno, "fase": r.fase, "num_operarios": r.num_operarios,
         "horas_programadas": r.horas_programadas, "horas_trabajadas": r.horas_trabajadas,
         "produccion_real": r.produccion_real, "produccion_std": r.produccion_std,
         "piezas_buenas": r.piezas_buenas, "disponibilidad": r.disponibilidad,
         "rendimiento": r.rendimiento, "calidad_pct": r.calidad_pct, "ole": r.ole}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 7. Fusionado
# ─────────────────────────────────────────────
class FusionadoIn(BaseModel):
    of_numero:     str
    fecha:         date
    turno:         str
    referencia:    str
    temperatura_c: float
    presion_kgcm2: float
    tiempo_seg:    float
    num_piezas:    int
    observacion:   Optional[str] = None


@router.post("/fusionado", status_code=201)
def crear_fusionado(data: FusionadoIn, db: Session = Depends(get_db)):
    rec = IngFusionadoParam(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/fusionado")
def listar_fusionado(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngFusionadoParam).order_by(IngFusionadoParam.id.desc())
    if of_numero:
        q = q.filter(IngFusionadoParam.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "of_numero": r.of_numero, "fecha": str(r.fecha),
         "turno": r.turno, "referencia": r.referencia,
         "temperatura_c": r.temperatura_c, "presion_kgcm2": r.presion_kgcm2,
         "tiempo_seg": r.tiempo_seg, "num_piezas": r.num_piezas, "observacion": r.observacion}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 8. Habilitado
# ─────────────────────────────────────────────
class HabilitadoIn(BaseModel):
    of_numero:          str
    fecha:              date
    turno:              str
    supervisor:         str
    prendas_cortadas:   int
    prendas_entregadas: int
    kit_completo:       str
    pct_entrega:        Optional[float] = None
    observacion:        Optional[str] = None


@router.post("/habilitado", status_code=201)
def crear_habilitado(data: HabilitadoIn, db: Session = Depends(get_db)):
    rec = IngHabilitadoCierre(**data.model_dump())
    rec.of_id = _resolve_of_id(db, data.of_numero)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/habilitado")
def listar_habilitado(of_numero: Optional[str] = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(IngHabilitadoCierre).order_by(IngHabilitadoCierre.id.desc())
    if of_numero:
        q = q.filter(IngHabilitadoCierre.of_numero == of_numero)
    rows = q.limit(limit).all()
    return [
        {"id": r.id, "of_numero": r.of_numero, "fecha": str(r.fecha),
         "turno": r.turno, "supervisor": r.supervisor,
         "prendas_cortadas": r.prendas_cortadas, "prendas_entregadas": r.prendas_entregadas,
         "kit_completo": r.kit_completo, "pct_entrega": r.pct_entrega, "observacion": r.observacion}
        for r in rows
    ]


# ─────────────────────────────────────────────
# 9. Ishikawa
# ─────────────────────────────────────────────
class IshikawaCausaIn(BaseModel):
    categoria:   str
    causa_texto: str
    porques:     list[str] = Field(default_factory=list)
    causa_raiz:  Optional[str] = None
    validada:    bool = False


class IshikawaCausaUpdate(BaseModel):
    porques:    Optional[list[str]] = None
    causa_raiz: Optional[str] = None
    validada:   Optional[bool] = None


@router.post("/ishikawa", status_code=201)
def crear_causa(data: IshikawaCausaIn, db: Session = Depends(get_db)):
    rec = IngIshikawaCausa(
        categoria=data.categoria,
        causa_texto=data.causa_texto,
        porques_json=json.dumps(data.porques),
        causa_raiz=data.causa_raiz,
        validada=data.validada,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "ok": True}


@router.get("/ishikawa")
def listar_causas(db: Session = Depends(get_db)):
    rows = db.query(IngIshikawaCausa).order_by(IngIshikawaCausa.categoria, IngIshikawaCausa.id).all()
    return [
        {"id": r.id, "categoria": r.categoria, "causa_texto": r.causa_texto,
         "porques": json.loads(r.porques_json) if r.porques_json else [],
         "causa_raiz": r.causa_raiz, "validada": r.validada}
        for r in rows
    ]


@router.patch("/ishikawa/{causa_id}")
def actualizar_causa(causa_id: int, data: IshikawaCausaUpdate, db: Session = Depends(get_db)):
    rec = db.query(IngIshikawaCausa).filter(IngIshikawaCausa.id == causa_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Causa no encontrada")
    if data.porques is not None:
        rec.porques_json = json.dumps(data.porques)
    if data.causa_raiz is not None:
        rec.causa_raiz = data.causa_raiz
    if data.validada is not None:
        rec.validada = data.validada
    db.commit()
    return {"ok": True}


@router.delete("/ishikawa/{causa_id}", status_code=204)
def eliminar_causa(causa_id: int, db: Session = Depends(get_db)):
    rec = db.query(IngIshikawaCausa).filter(IngIshikawaCausa.id == causa_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Causa no encontrada")
    db.delete(rec)
    db.commit()
