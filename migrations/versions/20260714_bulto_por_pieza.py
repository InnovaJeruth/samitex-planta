"""Bulto por pieza: of_paquetes gana pieza_id (bulto = talla + color + tipo de pieza)

Cambia el grano del bulto de 'prenda completa' a 'pieza'. Limpia los bultos
existentes (eran del grano viejo) y ajusta el único a (of_id, pieza_id, numero).

Revision ID: 20260714_bulto_por_pieza
Revises: 20260714_calidad_rechazos
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = '20260714_bulto_por_pieza'
down_revision = '20260714_calidad_rechazos'
branch_labels = None
depends_on = None

_OLD_UQ = 'uq_of_paquete_num'
_NEW_UQ = 'uq_of_paquete_pieza_num'


def _drop_uq(name):
    op.execute(sa.text(
        f"IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name='{name}' "
        f"AND parent_object_id=OBJECT_ID('of_paquetes')) "
        f"ALTER TABLE of_paquetes DROP CONSTRAINT {name}"))


def _add_uq(name, cols):
    op.execute(sa.text(
        f"IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name='{name}' "
        f"AND parent_object_id=OBJECT_ID('of_paquetes')) "
        f"ALTER TABLE of_paquetes ADD CONSTRAINT {name} UNIQUE ({cols})"))


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'of_paquetes' not in tablas:
        return
    mssql = bind.dialect.name == 'mssql'

    # 1) Limpiar bultos del grano viejo (y dependientes)
    for t in ('of_paquete_rechazos', 'of_paquete_eventos', 'of_paquetes'):
        if t in tablas:
            op.execute(sa.text(f"DELETE FROM {t}"))

    # 2) Columna pieza_id + FK + índice
    cols = {c['name'] for c in insp.get_columns('of_paquetes')}
    if 'pieza_id' not in cols:
        op.add_column('of_paquetes', sa.Column('pieza_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_of_paquete_pieza', 'of_paquetes', 'of_piezas',
                              ['pieza_id'], ['id'], ondelete='CASCADE')
        op.create_index('ix_of_paquetes_pieza', 'of_paquetes', ['pieza_id'])

    # 3) Reemplazar único (of_id, numero) → (of_id, pieza_id, numero)
    if mssql:
        _drop_uq(_OLD_UQ)
        _add_uq(_NEW_UQ, 'of_id, pieza_id, numero')
    else:
        try:
            op.drop_constraint(_OLD_UQ, 'of_paquetes', type_='unique')
        except Exception:
            pass
        op.create_unique_constraint(_NEW_UQ, 'of_paquetes', ['of_id', 'pieza_id', 'numero'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'of_paquetes' not in tablas:
        return
    mssql = bind.dialect.name == 'mssql'
    op.execute(sa.text("DELETE FROM of_paquetes"))
    if mssql:
        _drop_uq(_NEW_UQ)
    else:
        try:
            op.drop_constraint(_NEW_UQ, 'of_paquetes', type_='unique')
        except Exception:
            pass
    cols = {c['name'] for c in insp.get_columns('of_paquetes')}
    if 'pieza_id' in cols:
        op.drop_index('ix_of_paquetes_pieza', table_name='of_paquetes')
        op.drop_constraint('fk_of_paquete_pieza', 'of_paquetes', type_='foreignkey')
        op.drop_column('of_paquetes', 'pieza_id')
    if mssql:
        _add_uq(_OLD_UQ, 'of_id, numero')
    else:
        op.create_unique_constraint(_OLD_UQ, 'of_paquetes', ['of_id', 'numero'])
