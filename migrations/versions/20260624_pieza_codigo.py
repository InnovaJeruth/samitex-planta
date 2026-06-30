"""Agregar codigo a plantilla_piezas y codigo_pieza a of_piezas

Revision ID: pieza_codigo_v1
Revises: catalogo_tipo_cliente_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'pieza_codigo_v1'
down_revision: Union[str, None] = 'catalogo_tipo_cliente_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Agregar codigo nullable a plantilla_piezas ─────────────────────────
    op.add_column('plantilla_piezas',
        sa.Column('codigo', sa.String(50), nullable=True))

    # ── 2. Auto-generar códigos genéricos para piezas de prendas BASE ─────────
    #       Formato: {codigo_prenda_sin_guion}-P{orden+1:02d}
    #       Ej: SACO-BASE pieza orden 0 → SACO-BASE-P01
    op.execute(text("""
        UPDATE pp
        SET pp.codigo = pc.codigo + '-P' + RIGHT('0' + CAST(pp.orden + 1 AS VARCHAR), 2)
        FROM plantilla_piezas pp
        JOIN prendas_catalogo pc ON pc.id = pp.prenda_catalogo_id
        WHERE pc.tipo_cliente = 'BASE'
          AND pp.codigo IS NULL
    """))

    # ── 3. Para piezas de prendas no-BASE sin código (si hubiera), generar temporal
    op.execute(text("""
        UPDATE pp
        SET pp.codigo = pc.codigo + '-P' + RIGHT('0' + CAST(pp.orden + 1 AS VARCHAR), 2)
              + '-' + CAST(pp.id AS VARCHAR)
        FROM plantilla_piezas pp
        JOIN prendas_catalogo pc ON pc.id = pp.prenda_catalogo_id
        WHERE pp.codigo IS NULL
    """))

    # ── 4. Aplicar UNIQUE constraint ahora que todos tienen código ─────────────
    op.create_index('uq_plantilla_piezas_codigo', 'plantilla_piezas', ['codigo'], unique=True)

    # ── 5. Agregar codigo_pieza nullable a of_piezas (solo referencia) ─────────
    op.add_column('of_piezas',
        sa.Column('codigo_pieza', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('of_piezas', 'codigo_pieza')
    op.drop_index('uq_plantilla_piezas_codigo', 'plantilla_piezas')
    op.drop_column('plantilla_piezas', 'codigo')
