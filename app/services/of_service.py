# Servicio de logica de negocio para Ordenes de Fabricacion.
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, EstadoOF, EstadoDocsEnum
from app.services.gate_service import puede_activar


def actualizar_estado_docs(of: OrdenFabricacion, db: Session) -> None:
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
