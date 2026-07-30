"""SOLPED de tela: of_paquete_rechazos.solped (trazabilidad del rehacer con tela nueva)

Planeamiento registra el N° de SOLPED (SAP) del rollo pedido para rehacer. Una SOLPED
puede cubrir varias piezas. Es obligatorio antes de marcar 'tela recibida'.

Revision ID: 20260715_solped_tela
Revises: 20260715_rehacer_default
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_solped_tela'
down_revision = '20260715_rehacer_default'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'of_paquete_rechazos' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('of_paquete_rechazos')}
    if 'solped' not in cols:
        op.add_column('of_paquete_rechazos', sa.Column('solped', sa.String(length=40), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'of_paquete_rechazos' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('of_paquete_rechazos')}
    if 'solped' in cols:
        op.drop_column('of_paquete_rechazos', 'solped')
