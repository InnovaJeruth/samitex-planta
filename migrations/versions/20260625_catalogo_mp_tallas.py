"""catalogo_mp, prenda_mp_config y catalogo_tallas

Revision ID: 20260625_catalogo_mp_tallas
Revises: 20260625_catalogo_avios
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '20260625_catalogo_mp_tallas'
down_revision = '20260625_catalogo_avios'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'catalogo_mp',
        sa.Column('id',                 sa.Integer(),     nullable=False),
        sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
        sa.Column('nombre',             sa.String(200),   nullable=False),
        sa.Column('tipo',               sa.String(30),    nullable=False),
        sa.Column('ancho_referencia',   sa.Float(),       nullable=True),
        sa.Column('consumo_unitario',   sa.Float(),       nullable=False, server_default='1'),
        sa.Column('pct_adicional',      sa.Float(),       nullable=False, server_default='0.02'),
        sa.Column('unidad_medida',      sa.String(10),    nullable=False, server_default='mt.'),
        sa.Column('codigo_interno',     sa.String(50),    nullable=True),
        sa.Column('proveedor',          sa.String(150),   nullable=True),
        sa.Column('moneda',             sa.String(5),     nullable=True),
        sa.Column('precio_referencia',  sa.Float(),       nullable=True),
        sa.Column('orden',              sa.Integer(),     nullable=False, server_default='0'),
        sa.Column('activo',             sa.Boolean(),     nullable=False, server_default='1'),
        sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_catalogo_mp_id',     'catalogo_mp', ['id'])
    op.create_index('ix_catalogo_mp_prenda', 'catalogo_mp', ['prenda_catalogo_id'])

    op.create_table(
        'prenda_mp_config',
        sa.Column('id',                 sa.Integer(),     nullable=False),
        sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
        sa.Column('mp_id',              sa.Integer(),     nullable=False),
        sa.Column('codigo_cliente',     sa.String(50),    nullable=True),
        sa.Column('excluido',           sa.Boolean(),     nullable=False, server_default='0'),
        sa.Column('consumo_override',   sa.Float(),       nullable=True),
        sa.Column('notas',              sa.String(300),   nullable=True),
        sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.Column('updated_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mp_id'],              ['catalogo_mp.id'],      ondelete='NO ACTION'),
    )
    op.create_index('ix_prenda_mp_config_id',         'prenda_mp_config', ['id'])
    op.create_index('ix_prenda_mp_config_prenda',     'prenda_mp_config', ['prenda_catalogo_id'])
    op.create_index('ix_prenda_mp_config_prenda_mp',  'prenda_mp_config', ['prenda_catalogo_id', 'mp_id'], unique=True)

    op.create_table(
        'catalogo_tallas',
        sa.Column('id',                 sa.Integer(),     nullable=False),
        sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
        sa.Column('talla',              sa.String(20),    nullable=False),
        sa.Column('orden',              sa.Integer(),     nullable=False, server_default='0'),
        sa.Column('activo',             sa.Boolean(),     nullable=False, server_default='1'),
        sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_catalogo_tallas_id',     'catalogo_tallas', ['id'])
    op.create_index('ix_catalogo_tallas_prenda', 'catalogo_tallas', ['prenda_catalogo_id'])


def downgrade() -> None:
    op.drop_index('ix_catalogo_tallas_prenda', 'catalogo_tallas')
    op.drop_index('ix_catalogo_tallas_id',     'catalogo_tallas')
    op.drop_table('catalogo_tallas')

    op.drop_index('ix_prenda_mp_config_prenda_mp',  'prenda_mp_config')
    op.drop_index('ix_prenda_mp_config_prenda',     'prenda_mp_config')
    op.drop_index('ix_prenda_mp_config_id',         'prenda_mp_config')
    op.drop_table('prenda_mp_config')

    op.drop_index('ix_catalogo_mp_prenda', 'catalogo_mp')
    op.drop_index('ix_catalogo_mp_id',     'catalogo_mp')
    op.drop_table('catalogo_mp')
