"""Catálogo: base_id (jerarquía base → variante) + integridad

Aditivo. Agrega prendas_catalogo.base_id (self-FK) para ligar cada variante
(MARCA/INSTITUCION) con su prenda BASE. Índice + CHECK (una base no cuelga de otra).

Revision ID: 20260717_catalogo_base_id
Revises: 20260717_catalogo_material_sap
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = '20260717_catalogo_base_id'
down_revision = '20260717_catalogo_material_sap'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'prendas_catalogo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('prendas_catalogo')}
    if 'base_id' not in cols:
        op.add_column('prendas_catalogo', sa.Column('base_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_prendas_catalogo_base', 'prendas_catalogo', 'prendas_catalogo',
                              ['base_id'], ['id'])
        op.create_index('ix_prendas_catalogo_base', 'prendas_catalogo', ['base_id'])
        op.create_check_constraint(
            'ck_prenda_base_sin_padre', 'prendas_catalogo',
            "NOT (tipo_cliente = 'BASE' AND base_id IS NOT NULL)")


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'prendas_catalogo' not in set(insp.get_table_names()):
        return
    for fn in (lambda: op.drop_constraint('ck_prenda_base_sin_padre', 'prendas_catalogo', type_='check'),
               lambda: op.drop_index('ix_prendas_catalogo_base', table_name='prendas_catalogo'),
               lambda: op.drop_constraint('fk_prendas_catalogo_base', 'prendas_catalogo', type_='foreignkey'),
               lambda: op.drop_column('prendas_catalogo', 'base_id')):
        try:
            fn()
        except Exception:
            pass
