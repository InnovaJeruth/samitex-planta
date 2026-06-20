"""
Servicio de lógica de negocio para Órdenes de Fabricación.
"""
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, EstadoOF, EstadoDocsEnum
from app.services.gate_service import puede_activar


def actualizar_estado_docs(of: OrdenFabricacion, db: Session) -> None:
    """Recalcula estado_docs y activa la OF automáticamente si está completa.

    Reglas:
    - Si hay al menos 1 documento → pasa de PENDIENTE a EN_DOCUMENTACION.
    - Si todos los gates OK y OF en BORRADOR con piezas con codigo_sap → ACTIVA.
    """
    ok, _ = puede_activar(of, db)

    if of.documentos:
        if of.estado_docs == EstadoDocsEnum.PENDIENTE:
            of.estado_docs = EstadoDocsEnum.EN_DOCUMENTACION

    if ok and of.estado == EstadoOF.BORRADOR:
        of.estado_docs = EstadoDocsEnum.COMPLETA
        piezas_sin_sap = [p for p in of.piezas if not p.codigo_sap]
        if not piezas_sin_sap:
            of.estado = EstadoOF.ACTIVA

    db.commit()
