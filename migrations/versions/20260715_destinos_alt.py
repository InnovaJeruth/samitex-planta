"""Alternativas de destino: motivos_rechazo.destinos_alt + correcciones CR28/CR30

Casos "dos áreas de trabajo" donde Calidad elige (Corte/Modelista, Modelista/Tizado).
Casos "gerencia o merma/área" quedan en Gerencia (ella decide). Corrige CR28 y CR30 a
GERENCIA (CR09 ya estaba).

Revision ID: 20260715_destinos_alt
Revises: 20260715_destinos_defecto
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_destinos_alt'
down_revision = '20260715_destinos_defecto'
branch_labels = None
depends_on = None

# defecto -> alternativas (además del destino fijo)
ALTS = {
    "CR42": "MODELISTA", "CR43": "MODELISTA", "CR44": "MODELISTA",
    "CR47": "MODELISTA", "CR53": "TIZADO",
}
# correcciones de destino a Gerencia (ella decide/deriva)
A_GERENCIA = ("CR28", "CR30")


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'motivos_rechazo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('motivos_rechazo')}
    if 'destinos_alt' not in cols:
        op.add_column('motivos_rechazo', sa.Column('destinos_alt', sa.String(length=80), nullable=True))
    for codigo, alt in ALTS.items():
        op.execute(sa.text("UPDATE motivos_rechazo SET destinos_alt=:a WHERE codigo=:c")
                   .bindparams(a=alt, c=codigo))
    for codigo in A_GERENCIA:
        op.execute(sa.text("UPDATE motivos_rechazo SET destino='GERENCIA' WHERE codigo=:c")
                   .bindparams(c=codigo))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'motivos_rechazo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('motivos_rechazo')}
    if 'destinos_alt' in cols:
        op.drop_column('motivos_rechazo', 'destinos_alt')
