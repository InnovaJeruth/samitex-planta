"""
Agrega codigo_base a catalogo_mp y catalogo_avios para trazabilidad
de ítems propios de variante.
revision:      20260626_variante_items
down_revision: 20260626_composicion
"""
from alembic import op
import sqlalchemy as sa


revision      = '20260626_variante_items'
down_revision = '20260626_composicion'
branch_labels = None
depends_on    = None


def _col_exists(table, column):
    from sqlalchemy import inspect, text
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=:t AND COLUMN_NAME=:c"
    ), {"t": table, "c": column})
    return result.scalar() > 0


def upgrade():
    if not _col_exists("catalogo_mp", "codigo_base"):
        op.add_column("catalogo_mp",
            sa.Column("codigo_base", sa.String(60), nullable=True))

    if not _col_exists("catalogo_avios", "codigo_base"):
        op.add_column("catalogo_avios",
            sa.Column("codigo_base", sa.String(60), nullable=True))


def downgrade():
    op.drop_column("catalogo_avios", "codigo_base")
    op.drop_column("catalogo_mp",    "codigo_base")
