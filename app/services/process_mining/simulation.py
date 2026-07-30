"""Process Mining · datos para la simulación (replay) de UNA OF.

Devuelve la secuencia de fases de la OF con su duración REAL (minutos) y un
color por umbral, para que el front la reproduzca acelerada.

Colores (por ahora fijos; luego los reemplazarán los tiempos estándar):
    verde  < 15 min   ·   amarillo 15–60 min   ·   rojo > 60 min
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion
from app.models.fase import OFFaseTiempos
from app.models.paquete import (
    OFPaquete, OFPaqueteEvento, ESTADO_POR_VALIDAR, ESTADO_ENTREGADO,
)
from app.constants import NOMBRES_FASE

VERDE_MAX = 15      # < 15 min → verde
AMARILLO_MAX = 60   # 15–60 → amarillo ; > 60 → rojo


def _color(mins: Optional[float]) -> str:
    if mins is None:
        return "gris"
    if mins > AMARILLO_MAX:
        return "rojo"
    if mins >= VERDE_MAX:
        return "amarillo"
    return "verde"


def _dur(ini, fin) -> Optional[float]:
    if ini and fin:
        return round((fin - ini).total_seconds() / 60.0, 1)
    return None


def _fase(nombre, ini, fin) -> Optional[dict]:
    m = _dur(ini, fin)
    if m is None:
        return None
    return {"fase": nombre, "min": m, "color": _color(m),
            "inicio": ini.isoformat(), "fin": fin.isoformat()}


def simulacion_of(db: Session, of_id: int) -> dict:
    """Secuencia de fases (Tizado→…→Calidad) de la OF con duración real y color."""
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    numero = of.numero_of if of else str(of_id)

    tiempos = {t.fase_id: t for t in
               db.query(OFFaseTiempos).filter_by(of_id=of_id).all()}
    fases = []
    inicios, fines = [], []   # para el lead time real (reloj de pared)

    def _agregar(nombre, ini, fin):
        f = _fase(nombre, ini, fin)
        if f:
            fases.append(f)
            inicios.append(ini)
            fines.append(fin)

    # Tela + numeración (F1–F4) desde of_fase_tiempos
    for fid in ["F1", "F2", "F3", "F4"]:
        t = tiempos.get(fid)
        if t:
            _agregar(NOMBRES_FASE.get(fid, fid), t.inicio_real, t.fin_real)

    # Fusionado (agregado): min inicio → max fin de los bultos
    f_ini, f_fin = (db.query(func.min(OFPaquete.fusionado_inicio),
                             func.max(OFPaquete.fusionado_fin))
                    .filter(OFPaquete.of_id == of_id).first())
    _agregar("Fusionado", f_ini, f_fin)

    # Calidad: primer "enviado a calidad" → último "liberado"
    cal_ini = (db.query(func.min(OFPaqueteEvento.created_at))
               .join(OFPaquete, OFPaquete.id == OFPaqueteEvento.paquete_id)
               .filter(OFPaquete.of_id == of_id,
                       OFPaqueteEvento.estado == ESTADO_POR_VALIDAR).scalar())
    cal_fin = (db.query(func.max(OFPaqueteEvento.created_at))
               .join(OFPaquete, OFPaquete.id == OFPaqueteEvento.paquete_id)
               .filter(OFPaquete.of_id == of_id,
                       OFPaqueteEvento.estado == ESTADO_ENTREGADO).scalar())
    _agregar("Calidad", cal_ini, cal_fin)

    # total_min = suma de fases (impulsa la animación, proporción de cada caja)
    total = round(sum(x["min"] for x in fases), 1) if fases else 0.0
    # lead_time_real_min = reloj de pared (min inicio → max fin) → coincide con la ruta crítica
    lead_real = round((max(fines) - min(inicios)).total_seconds() / 60.0, 1) if inicios else 0.0
    return {"of_id": of_id, "numero_of": numero, "fases": fases,
            "total_min": total, "lead_time_real_min": lead_real}
