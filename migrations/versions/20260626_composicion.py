"""Agrega columna composicion a prendas_catalogo"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision      = '20260626_composicion'
down_revision = '20260626_safe_sync'
branch_labels = None
depends_on    = None


def _col_exists(table, column):
    conn = op.get_bind()
    r = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=:t AND COLUMN_NAME=:c"
    ), {"t": table, "c": column})
    return r.scalar() > 0


def upgrade():
    if not _col_exists('prendas_catalogo', 'composicion'):
        op.add_column('prendas_catalogo',
            sa.Column('composicion', sa.String(200), nullable=True))


def downgrade():
    try:
        op.drop_column('prendas_catalogo', 'composicion')
    except Exception:
        pass
