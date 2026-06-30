"""Renombrar tipo_base OTRO -> PULLOVER en catálogo y OFs

Revision ID: otro_to_pullover_v1
Revises: catalogo_fit_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
from sqlalchemy import text

revision: str = 'otro_to_pullover_v1'
down_revision: Union[str, None] = 'catalogo_fit_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Actualizar prendas_catalogo
    op.execute(text("""
        UPDATE prendas_catalogo
        SET tipo_base = 'PULLOVER',
            nombre    = REPLACE(nombre,    'Otro', 'Pullover'),
            codigo    = REPLACE(codigo,    'OTRO', 'PULL')
        WHERE tipo_base = 'OTRO'
    """))

    # Actualizar ordenes_fabricacion con tipo_prenda = 'OTRO'
    op.execute(text("""
        UPDATE ordenes_fabricacion
        SET tipo_prenda = 'PULLOVER'
        WHERE tipo_prenda = 'OTRO'
    """))


def downgrade() -> None:
    op.execute(text("""
        UPDATE prendas_catalogo
        SET tipo_base = 'OTRO',
            nombre    = REPLACE(nombre,    'Pullover', 'Otro'),
            codigo    = REPLACE(codigo,    'PULL',     'OTRO')
        WHERE tipo_base = 'PULLOVER'
          AND creado_por_rol = 'SISTEMA'
    """))
    op.execute(text("""
        UPDATE ordenes_fabricacion
        SET tipo_prenda = 'OTRO'
        WHERE tipo_prenda = 'PULLOVER'
    """))
