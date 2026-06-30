"""Agregar tipo_cliente a prendas_catalogo (INSTITUCION | MARCA | BASE)

Revision ID: catalogo_tipo_cliente_v1
Revises: otro_to_pullover_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'catalogo_tipo_cliente_v1'
down_revision: Union[str, None] = 'otro_to_pullover_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('prendas_catalogo',
        sa.Column('tipo_cliente', sa.String(20), nullable=False, server_default='BASE'))

    # Las 4 prendas base (creado_por_rol = 'SISTEMA') quedan como BASE
    op.execute(text("""
        UPDATE prendas_catalogo
        SET tipo_cliente = 'BASE'
        WHERE creado_por_rol = 'SISTEMA'
    """))


def downgrade() -> None:
    op.drop_column('prendas_catalogo', 'tipo_cliente')
