from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.database.connection import Base


class ParametroSistema(Base):
    """Parámetros configurables del sistema (clave-valor)."""
    __tablename__ = "parametros_sistema"

    clave       = Column(String(50),   primary_key=True)
    valor       = Column(String(255),  nullable=False)
    descripcion = Column(String(500),  nullable=True)
    updated_at  = Column(DateTime,     server_default=func.now(), onupdate=func.now())

    @classmethod
    def get(cls, db, clave: str, default=None):
        """Lee un parámetro por clave. Retorna default si no existe o falla."""
        try:
            row = db.query(cls).filter_by(clave=clave).first()
            return row.valor if row else default
        except Exception:
            return default

    @classmethod
    def set(cls, db, clave: str, valor: str):
        """Crea o actualiza un parámetro."""
        row = db.query(cls).filter_by(clave=clave).first()
        if row:
            row.valor = valor
        else:
            db.add(cls(clave=clave, valor=valor))
        db.commit()
