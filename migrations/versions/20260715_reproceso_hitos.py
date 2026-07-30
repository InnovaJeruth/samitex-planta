"""Ruta de rehacer: of_paquete_rechazos.etapa + tabla of_reproceso_hitos (trazabilidad)

Stepper de re-fabricación (Tizado→Tendido→Corte→Numerado→[Fusionado]→Calidad) con hora
por etapa.

Revision ID: 20260715_reproceso_hitos
Revises: 20260715_solped_tela
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_reproceso_hitos'
down_revision = '20260715_solped_tela'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if 'of_paquete_rechazos' in tablas:
        cols = {c['name'] for c in insp.get_columns('of_paquete_rechazos')}
        if 'etapa' not in cols:
            op.add_column('of_paquete_rechazos', sa.Column('etapa', sa.String(length=15), nullable=True))

    if 'of_reproceso_hitos' not in tablas:
        op.create_table(
            'of_reproceso_hitos',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('rechazo_id', sa.Integer(),
                      sa.ForeignKey('of_paquete_rechazos.id', ondelete='CASCADE'), nullable=False),
            sa.Column('etapa', sa.String(length=15), nullable=False),
            sa.Column('at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        )
        op.create_index('ix_of_reproceso_hitos_rechazo', 'of_reproceso_hitos', ['rechazo_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'of_reproceso_hitos' in tablas:
        op.drop_index('ix_of_reproceso_hitos_rechazo', table_name='of_reproceso_hitos')
        op.drop_table('of_reproceso_hitos')
    if 'of_paquete_rechazos' in tablas:
        cols = {c['name'] for c in insp.get_columns('of_paquete_rechazos')}
        if 'etapa' in cols:
            op.drop_column('of_paquete_rechazos', 'etapa')
