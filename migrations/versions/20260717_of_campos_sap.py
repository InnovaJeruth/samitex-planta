"""OF: campos de origen SAP + fecha_sap a DateTime

Aditivo. Agrega a ordenes_fabricacion los datos que trae el export de la COIS:
material_sap, clase_orden, centro, sociedad, area_planificacion, almacen, autor_sap.
Cambia fecha_sap de Date a DateTime (fecha inicio extrema + hora creación).

Revision ID: 20260717_of_campos_sap
Revises: 20260716_hoja_numeracion_cierre
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = '20260717_of_campos_sap'
down_revision = '20260716_hoja_numeracion_cierre'
branch_labels = None
depends_on = None

_COLS = {
    'material_sap':       sa.String(length=30),
    'clase_orden':        sa.String(length=10),
    'centro':             sa.String(length=10),
    'sociedad':           sa.String(length=10),
    'area_planificacion': sa.String(length=10),
    'almacen':            sa.String(length=10),
    'autor_sap':          sa.String(length=30),
}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'ordenes_fabricacion' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
    for name, tipo in _COLS.items():
        if name not in cols:
            op.add_column('ordenes_fabricacion', sa.Column(name, tipo, nullable=True))
    op.create_index('ix_ordenes_fabricacion_material_sap', 'ordenes_fabricacion', ['material_sap'])
    # fecha_sap: Date -> DateTime (conserva la fecha; la hora se completará en el import)
    try:
        op.alter_column('ordenes_fabricacion', 'fecha_sap',
                        existing_type=sa.Date(), type_=sa.DateTime(), existing_nullable=True)
    except Exception:
        pass  # motores que no soportan alter_column (ej. SQLite) — el modelo ya define DateTime


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'ordenes_fabricacion' not in set(insp.get_table_names()):
        return
    try:
        op.alter_column('ordenes_fabricacion', 'fecha_sap',
                        existing_type=sa.DateTime(), type_=sa.Date(), existing_nullable=True)
    except Exception:
        pass
    try:
        op.drop_index('ix_ordenes_fabricacion_material_sap', table_name='ordenes_fabricacion')
    except Exception:
        pass
    cols = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
    for name in reversed(list(_COLS)):
        if name in cols:
            op.drop_column('ordenes_fabricacion', name)
