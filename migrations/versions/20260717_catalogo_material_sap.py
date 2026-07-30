"""Catálogo: material_sap (llave con OF) + familia + bom_sap + estado_ficha

Aditivo. Prepara PrendaCatalogo para enlazar con la OF por número de material
SAP y para marcar el estado de la ficha técnica (pendiente/completa).

Revision ID: 20260717_catalogo_material_sap
Revises: 20260717_of_campos_sap
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = '20260717_catalogo_material_sap'
down_revision = '20260717_of_campos_sap'
branch_labels = None
depends_on = None

_COLS = {
    'material_sap': sa.String(length=30),
    'familia':      sa.String(length=120),
    'bom_sap':      sa.String(length=30),
    'estado_ficha': sa.String(length=15),
}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'prendas_catalogo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('prendas_catalogo')}
    for name, tipo in _COLS.items():
        if name not in cols:
            if name == 'estado_ficha':
                op.add_column('prendas_catalogo',
                              sa.Column(name, tipo, nullable=False, server_default='PENDIENTE'))
            else:
                op.add_column('prendas_catalogo', sa.Column(name, tipo, nullable=True))
    op.create_index('ux_prendas_catalogo_material_sap', 'prendas_catalogo',
                    ['material_sap'], unique=True,
                    mssql_where=sa.text('material_sap IS NOT NULL'))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'prendas_catalogo' not in set(insp.get_table_names()):
        return
    try:
        op.drop_index('ux_prendas_catalogo_material_sap', table_name='prendas_catalogo')
    except Exception:
        pass
    cols = {c['name'] for c in insp.get_columns('prendas_catalogo')}
    for name in reversed(list(_COLS)):
        if name in cols:
            op.drop_column('prendas_catalogo', name)
