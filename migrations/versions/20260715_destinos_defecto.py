"""Destinos por defecto: motivos_rechazo.destino + of_paquete_rechazos.destino/rehacer

Ruteo real por área (del Excel + reunión con Calidad). El destino de cada defecto
es una sugerencia editable; el rechazo guarda el destino elegido y si es 'rehacer'
(corta nueva, usa tela).

Revision ID: 20260715_destinos_defecto
Revises: 20260715_fusionado_tiempos
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_destinos_defecto'
down_revision = '20260715_fusionado_tiempos'
branch_labels = None
depends_on = None

DESTINOS = {
    "CR01": "MODELISTA", "CR02": "MODELISTA", "CR03": "MODELISTA", "CR04": "EXTERNO",
    "CR05": "CORTE", "CR06": "CORTE", "CR07": "GERENCIA", "CR08": "GERENCIA",
    "CR09": "GERENCIA", "CR10": "CORTE", "CR11": "GERENCIA", "CR12": "FUSIONADO",
    "CR13": "MERMA", "CR14": "TENDIDO", "CR15": "TENDIDO", "CR16": "CORTE",
    "CR17": "CORTE", "CR18": "CORTE", "CR19": "CORTE", "CR20": "CORTE", "CR21": "CORTE",
    "CR22": "DESMANCHADO", "CR23": "FUSIONADO", "CR24": "FUSIONADO", "CR25": "HABILITADO",
    "CR26": "CORTE", "CR27": "MODELISTA", "CR28": "MODELISTA", "CR29": "CORTE",
    "CR30": "CORTE", "CR31": "CORTE", "CR32": "CORTE", "CR33": "CORTE", "CR34": "CORTE",
    "CR35": "CORTE", "CR36": "CORTE", "CR37": "CORTE", "CR38": "CORTE", "CR39": "GERENCIA",
    "CR40": "GERENCIA", "CR41": "GERENCIA", "CR42": "CORTE", "CR43": "CORTE", "CR44": "CORTE",
    "CR45": "MODELISTA", "CR46": "FUSIONADO", "CR47": "CORTE", "CR48": "TENDIDO",
    "CR49": "TIZADO", "CR50": "TIZADO", "CR51": "TIZADO", "CR52": "TENDIDO", "CR53": "MODELISTA",
}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if 'motivos_rechazo' in tablas:
        cols = {c['name'] for c in insp.get_columns('motivos_rechazo')}
        if 'destino' not in cols:
            op.add_column('motivos_rechazo', sa.Column('destino', sa.String(length=20), nullable=True))
        for codigo, destino in DESTINOS.items():
            op.execute(sa.text("UPDATE motivos_rechazo SET destino=:d WHERE codigo=:c")
                       .bindparams(d=destino, c=codigo))

    if 'of_paquete_rechazos' in tablas:
        cols = {c['name'] for c in insp.get_columns('of_paquete_rechazos')}
        if 'destino' not in cols:
            op.add_column('of_paquete_rechazos', sa.Column('destino', sa.String(length=20), nullable=True))
        if 'rehacer' not in cols:
            op.add_column('of_paquete_rechazos',
                          sa.Column('rehacer', sa.Boolean(), nullable=False, server_default=sa.text('0')))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'of_paquete_rechazos' in tablas:
        cols = {c['name'] for c in insp.get_columns('of_paquete_rechazos')}
        if 'rehacer' in cols:
            op.drop_column('of_paquete_rechazos', 'rehacer')
        if 'destino' in cols:
            op.drop_column('of_paquete_rechazos', 'destino')
    if 'motivos_rechazo' in tablas:
        cols = {c['name'] for c in insp.get_columns('motivos_rechazo')}
        if 'destino' in cols:
            op.drop_column('motivos_rechazo', 'destino')
