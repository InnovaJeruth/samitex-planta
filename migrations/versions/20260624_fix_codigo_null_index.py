"""Reemplazar unique index de codigo por filtered index (permite multiples NULL)

SQL Server solo permite UN NULL en un unique index estándar.
Para piezas heredadas sin código asignado necesitamos múltiples NULL.
La solución es un filtered unique index: WHERE codigo IS NOT NULL

Revision ID: fix_codigo_null_index_v1
Revises: prenda_documentos_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
from sqlalchemy import text

revision: str = 'fix_codigo_null_index_v1'
down_revision: Union[str, None] = 'prenda_documentos_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eliminar el unique index estándar (solo permite 1 NULL en SQL Server)
    op.execute(text("""
        IF EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE name = 'uq_plantilla_piezas_codigo'
              AND object_id = OBJECT_ID('plantilla_piezas')
        )
            DROP INDEX uq_plantilla_piezas_codigo ON plantilla_piezas
    """))

    # Crear filtered unique index: solo aplica cuando codigo NO es NULL
    # Esto permite múltiples filas con codigo=NULL (piezas heredadas sin código aún)
    op.execute(text("""
        CREATE UNIQUE INDEX uq_plantilla_piezas_codigo
        ON plantilla_piezas (codigo)
        WHERE codigo IS NOT NULL
    """))


def downgrade() -> None:
    op.execute(text("DROP INDEX uq_plantilla_piezas_codigo ON plantilla_piezas"))
    op.execute(text("""
        CREATE UNIQUE INDEX uq_plantilla_piezas_codigo
        ON plantilla_piezas (codigo)
    """))
