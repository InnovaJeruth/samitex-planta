"""Índices en FKs muy consultadas (aditivo, sin cambio de datos).

Añade índices individuales donde no existían y que se filtran constantemente:
  - of_piezas.of_id            (piezas por OF, ruta caliente)
  - documentos_of.of_id        (documentos/gates por OF)
  - of_fases_estado.pieza_id   (no cubierto por el compuesto of_id,fase_id)
  - avance_registros.pieza_id  (historial por pieza)

NO se tocan of_id de of_fases_estado / of_fase_tiempos: ya están cubiertos por
el prefijo izquierdo de sus índices compuestos / unique existentes.

Revision ID: 20260720_fk_indices
Revises: 20260718_costo_servicios_mod
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = '20260720_fk_indices'
down_revision = '20260718_costo_servicios_mod'
branch_labels = None
depends_on = None

# (nombre_indice, tabla, columna)
_INDICES = [
    ('ix_of_piezas_of_id',           'of_piezas',        'of_id'),
    ('ix_documentos_of_of_id',       'documentos_of',    'of_id'),
    ('ix_of_fases_estado_pieza_id',  'of_fases_estado',  'pieza_id'),
    ('ix_avance_registros_pieza_id', 'avance_registros', 'pieza_id'),
]


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for nombre, tabla, col in _INDICES:
        if tabla not in insp.get_table_names():
            continue
        existentes = {ix['name'] for ix in insp.get_indexes(tabla)}
        if nombre not in existentes:
            op.create_index(nombre, tabla, [col])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for nombre, tabla, _col in _INDICES:
        if tabla not in insp.get_table_names():
            continue
        existentes = {ix['name'] for ix in insp.get_indexes(tabla)}
        if nombre in existentes:
            op.drop_index(nombre, table_name=tabla)
