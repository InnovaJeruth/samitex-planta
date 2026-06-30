"""catalogo_avios y prenda_avio_config

Revision ID: 20260625_catalogo_avios
Revises:
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = '20260625_catalogo_avios'
down_revision = 'fases_estado_extra_cols_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'catalogo_avios',
        sa.Column('id',                 sa.Integer(),     nullable=False),
        sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
        sa.Column('seccion',            sa.String(20),    nullable=False),
        sa.Column('nombre',             sa.String(200),   nullable=False),
        sa.Column('codigo_interno',     sa.String(50),    nullable=True),
        sa.Column('proveedor',          sa.String(150),   nullable=True),
        sa.Column('procedencia',        sa.String(20),    nullable=True),
        sa.Column('unidad_medida',      sa.String(20),    nullable=False, server_default='Unid'),
        sa.Column('consumo_unitario',   sa.Float(),       nullable=False, server_default='1'),
        sa.Column('pct_adicional',      sa.Float(),       nullable=False, server_default='0.01'),
        sa.Column('unidad_compra',      sa.String(20),    nullable=True),
        sa.Column('moneda',             sa.String(5),     nullable=True),
        sa.Column('precio',             sa.Float(),       nullable=True),
        sa.Column('orden',              sa.Integer(),     nullable=False, server_default='0'),
        sa.Column('activo',             sa.Boolean(),     nullable=False, server_default='1'),
        sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_catalogo_avios_id',             'catalogo_avios', ['id'])
    op.create_index('ix_catalogo_avios_prenda_id',      'catalogo_avios', ['prenda_catalogo_id'])
    op.create_index('ix_catalogo_avios_prenda_sec',     'catalogo_avios', ['prenda_catalogo_id', 'seccion'])

    op.create_table(
        'prenda_avio_config',
        sa.Column('id',                 sa.Integer(),     nullable=False),
        sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
        sa.Column('avio_id',            sa.Integer(),     nullable=False),
        sa.Column('codigo_cliente',     sa.String(50),    nullable=True),
        sa.Column('excluido',           sa.Boolean(),     nullable=False, server_default='0'),
        sa.Column('consumo_override',   sa.Float(),       nullable=True),
        sa.Column('notas',              sa.String(300),   nullable=True),
        sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.Column('updated_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['avio_id'],            ['catalogo_avios.id'],   ondelete='CASCADE'),
    )
    op.create_index('ix_prenda_avio_config_id',           'prenda_avio_config', ['id'])
    op.create_index('ix_prenda_avio_config_prenda',       'prenda_avio_config', ['prenda_catalogo_id'])
    op.create_index('ix_prenda_avio_config_prenda_avio',  'prenda_avio_config', ['prenda_catalogo_id', 'avio_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_prenda_avio_config_prenda_avio', 'prenda_avio_config')
    op.drop_index('ix_prenda_avio_config_prenda',      'prenda_avio_config')
    op.drop_index('ix_prenda_avio_config_id',          'prenda_avio_config')
    op.drop_table('prenda_avio_config')

    op.drop_index('ix_catalogo_avios_prenda_sec',  'catalogo_avios')
    op.drop_index('ix_catalogo_avios_prenda_id',   'catalogo_avios')
    op.drop_index('ix_catalogo_avios_id',          'catalogo_avios')
    op.drop_table('catalogo_avios')
