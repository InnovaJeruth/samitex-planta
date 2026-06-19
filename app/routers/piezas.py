from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.pieza import OFPieza, PlantillaPieza
from app.models.of import TipoPrendaEnum
from app.models.usuario import Usuario
from app.core.auth import get_current_user

router = APIRouter()


@router.get("/plantillas/{tipo_prenda}")
def get_plantilla(tipo_prenda: str, db: Session = Depends(get_db)):
    plantillas = db.query(PlantillaPieza).filter_by(
        tipo_prenda=tipo_prenda.upper()
    ).order_by(PlantillaPieza.orden).all()
    return [
        {
            "nombre": p.nombre,
            "material_default": p.material_default,
            "cantidad_x_prenda": p.cantidad_x_prenda,
            "fusionado_default": p.fusionado_default,
        }
        for p in plantillas
    ]


@router.patch("/{pieza_id}/sap")
def actualizar_sap(
    pieza_id: int,
    codigo_sap: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    pieza = db.query(OFPieza).filter_by(id=pieza_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    pieza.codigo_sap = codigo_sap
    db.commit()
    return {"id": pieza.id, "codigo_sap": pieza.codigo_sap}


@router.delete("/{pieza_id}")
def eliminar_pieza(
    pieza_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in {"ADMIN", "PLANEADOR"}:
        raise HTTPException(403, "Solo ADMIN o PLANEADOR pueden eliminar piezas")
    pieza = db.query(OFPieza).filter_by(id=pieza_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    db.delete(pieza)
    db.commit()
    return {"mensaje": "Pieza eliminada"}
