"""Normalización: quitar planta_externa/fase_tercerizada, agregar of_id a fichas ing_

- ordenes_fabricacion.planta_externa: eliminada (duplicaba plantas_externas.nombre).
- ordenes_fabricacion.fase_tercerizada: columna huérfana (ya no en el modelo) — se elimina si existe.
- ing_*: se agrega of_id (FK opcional a ordenes_fabricacion) manteniendo of_numero
  como clave de negocio para las fichas de llenado libre.

Nota: en un entorno recreado (drop + create_all) esta revisión se aplica con
`alembic stamp head`; en un entorno ya en uso, con `alembic upgrade head`.

Revision ID: 20260709_normaliz
Revises: 20260709_avance_sku
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_normaliz'
down_revision = '20260709_avance_sku'
branch_labels = None
depends_on = None

ING_TABLES = [
    'ing_sam_registros',
    'ing_paradas_registro',
    'ing_muestreo_obs',
    'ing_tendido_fichas',
    'ing_calidad_inspeccion',
    'ing_ole_diario',
    'ing_fusionado_params',
    'ing_habilitado_cierre',
]


def _cols(insp, table):
    return {c['name'] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    of_cols = _cols(insp, 'ordenes_fabricacion')

    if 'planta_externa' in of_cols:
        op.drop_column('ordenes_fabricacion', 'planta_externa')
    if 'fase_tercerizada' in of_cols:
        op.drop_column('ordenes_fabricacion', 'fase_tercerizada')

    existentes = set(insp.get_table_names())
    for t in ING_TABLES:
        if t in existentes and 'of_id' not in _cols(insp, t):
            op.add_column(t, sa.Column('of_id', sa.Integer(), nullable=True))
            op.create_foreign_key(f'fk_{t}_of', t, 'ordenes_fabricacion', ['of_id'], ['id'])
            op.create_index(f'ix_{t}_of_id', t, ['of_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existentes = set(insp.get_table_names())
    for t in ING_TABLES:
        if t in existentes and 'of_id' in _cols(insp, t):
            op.drop_index(f'ix_{t}_of_id', table_name=t)
            op.drop_constraint(f'fk_{t}_of', t, type_='foreignkey')
            op.drop_column(t, 'of_id')

    op.add_column('ordenes_fabricacion',
                  sa.Column('planta_externa', sa.String(length=120), nullable=True))
