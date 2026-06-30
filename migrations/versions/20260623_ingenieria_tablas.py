"""Tablas de ingeniería industrial (ing_ prefix)

Revision ID: ingenieria_tablas_v1
Revises: bloque2_duracion_horas
Create Date: 2026-06-23
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = 'ingenieria_tablas_v1'
down_revision: Union[str, None] = 'bloque2_duracion_horas'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ing_sam_registros
    op.create_table(
        'ing_sam_registros',
        sa.Column('id',                sa.Integer(),     nullable=False),
        sa.Column('of_numero',         sa.String(50),    nullable=False),
        sa.Column('fecha',             sa.Date(),        nullable=False),
        sa.Column('operario',          sa.String(100),   nullable=False),
        sa.Column('fase',              sa.String(50),    nullable=False),
        sa.Column('elemento',          sa.String(200),   nullable=False),
        sa.Column('tiempos_json',      sa.Text(),        nullable=True),
        sa.Column('factor_valoracion', sa.Float(),       nullable=False, server_default='100'),
        sa.Column('suplementos_pct',   sa.Float(),       nullable=False, server_default='15'),
        sa.Column('tiempo_normal',     sa.Float(),       nullable=True),
        sa.Column('sam',               sa.Float(),       nullable=True),
        sa.Column('created_at',        sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_sam_registros_id',       'ing_sam_registros', ['id'])
    op.create_index('ix_ing_sam_of_fecha',           'ing_sam_registros', ['of_numero', 'fecha'])

    # 2. ing_paradas_registro
    op.create_table(
        'ing_paradas_registro',
        sa.Column('id',           sa.Integer(),    nullable=False),
        sa.Column('of_numero',    sa.String(50),   nullable=False),
        sa.Column('fecha',        sa.Date(),       nullable=False),
        sa.Column('turno',        sa.String(20),   nullable=False),
        sa.Column('fase',         sa.String(50),   nullable=False),
        sa.Column('causa',        sa.String(100),  nullable=False),
        sa.Column('duracion_min', sa.Float(),      nullable=False),
        sa.Column('observacion',  sa.Text(),       nullable=True),
        sa.Column('created_at',   sa.DateTime(),   server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_paradas_registro_id',    'ing_paradas_registro', ['id'])
    op.create_index('ix_ing_paradas_of_fecha',       'ing_paradas_registro', ['of_numero', 'fecha'])

    # 3. ing_muestreo_obs
    op.create_table(
        'ing_muestreo_obs',
        sa.Column('id',          sa.Integer(),    nullable=False),
        sa.Column('of_numero',   sa.String(50),   nullable=False),
        sa.Column('fecha',       sa.Date(),       nullable=False),
        sa.Column('hora',        sa.String(10),   nullable=False),
        sa.Column('fase',        sa.String(50),   nullable=False),
        sa.Column('estado',      sa.String(30),   nullable=False),
        sa.Column('observacion', sa.Text(),       nullable=True),
        sa.Column('created_at',  sa.DateTime(),   server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_muestreo_obs_id',        'ing_muestreo_obs', ['id'])
    op.create_index('ix_ing_muestreo_of_fecha',      'ing_muestreo_obs', ['of_numero', 'fecha'])

    # 4. ing_tendido_fichas
    op.create_table(
        'ing_tendido_fichas',
        sa.Column('id',                   sa.Integer(),  nullable=False),
        sa.Column('fecha',                sa.Date(),     nullable=False),
        sa.Column('of_numero',            sa.String(50), nullable=False),
        sa.Column('tipo_prenda',          sa.String(100),nullable=False),
        sa.Column('tela_partida',         sa.String(100),nullable=False),
        sa.Column('largo_tender_m',       sa.Float(),    nullable=False),
        sa.Column('num_capas',            sa.Integer(),  nullable=False),
        sa.Column('ancho_tela_m',         sa.Float(),    nullable=False),
        sa.Column('num_prendas',          sa.Integer(),  nullable=False),
        sa.Column('retazo_kg',            sa.Float(),    nullable=False, server_default='0'),
        sa.Column('area_tizado_m2',       sa.Float(),    nullable=False),
        sa.Column('pct_aprovechamiento',  sa.Float(),    nullable=True),
        sa.Column('area_tendida_m2',      sa.Float(),    nullable=True),
        sa.Column('created_at',           sa.DateTime(), server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_tendido_fichas_id',      'ing_tendido_fichas', ['id'])
    op.create_index('ix_ing_tendido_of_fecha',       'ing_tendido_fichas', ['of_numero', 'fecha'])

    # 5. ing_calidad_inspeccion
    op.create_table(
        'ing_calidad_inspeccion',
        sa.Column('id',                   sa.Integer(),  nullable=False),
        sa.Column('fecha',                sa.Date(),     nullable=False),
        sa.Column('of_numero',            sa.String(50), nullable=False),
        sa.Column('tipo_prenda',          sa.String(100),nullable=False),
        sa.Column('total_inspeccionado',  sa.Integer(),  nullable=False),
        sa.Column('def_mal_corte',        sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('def_fusionado',        sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('def_numeracion',       sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('def_tela',             sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('def_medida',           sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('def_otro',             sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('total_defectos',       sa.Integer(),  nullable=True),
        sa.Column('aprobadas',            sa.Integer(),  nullable=True),
        sa.Column('fpy',                  sa.Float(),    nullable=True),
        sa.Column('created_at',           sa.DateTime(), server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_calidad_inspeccion_id',  'ing_calidad_inspeccion', ['id'])
    op.create_index('ix_ing_calidad_of_fecha',       'ing_calidad_inspeccion', ['of_numero', 'fecha'])

    # 6. ing_ole_diario
    op.create_table(
        'ing_ole_diario',
        sa.Column('id',                sa.Integer(),  nullable=False),
        sa.Column('of_numero',         sa.String(50), nullable=False),
        sa.Column('fecha',             sa.Date(),     nullable=False),
        sa.Column('turno',             sa.String(20), nullable=False),
        sa.Column('fase',              sa.String(50), nullable=False),
        sa.Column('num_operarios',     sa.Integer(),  nullable=False),
        sa.Column('horas_programadas', sa.Float(),    nullable=False),
        sa.Column('horas_trabajadas',  sa.Float(),    nullable=False),
        sa.Column('produccion_real',   sa.Integer(),  nullable=False),
        sa.Column('produccion_std',    sa.Integer(),  nullable=False),
        sa.Column('piezas_buenas',     sa.Integer(),  nullable=False),
        sa.Column('disponibilidad',    sa.Float(),    nullable=True),
        sa.Column('rendimiento',       sa.Float(),    nullable=True),
        sa.Column('calidad_pct',       sa.Float(),    nullable=True),
        sa.Column('ole',               sa.Float(),    nullable=True),
        sa.Column('created_at',        sa.DateTime(), server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_ole_diario_id',          'ing_ole_diario', ['id'])
    op.create_index('ix_ing_ole_of_fecha',           'ing_ole_diario', ['of_numero', 'fecha'])

    # 7. ing_fusionado_params
    op.create_table(
        'ing_fusionado_params',
        sa.Column('id',            sa.Integer(),    nullable=False),
        sa.Column('of_numero',     sa.String(50),   nullable=False),
        sa.Column('fecha',         sa.Date(),       nullable=False),
        sa.Column('turno',         sa.String(20),   nullable=False),
        sa.Column('referencia',    sa.String(200),  nullable=False),
        sa.Column('temperatura_c', sa.Float(),      nullable=False),
        sa.Column('presion_kgcm2', sa.Float(),      nullable=False),
        sa.Column('tiempo_seg',    sa.Float(),      nullable=False),
        sa.Column('num_piezas',    sa.Integer(),    nullable=False),
        sa.Column('observacion',   sa.Text(),       nullable=True),
        sa.Column('created_at',    sa.DateTime(),   server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_fusionado_params_id',    'ing_fusionado_params', ['id'])
    op.create_index('ix_ing_fusion_of_fecha',        'ing_fusionado_params', ['of_numero', 'fecha'])

    # 8. ing_habilitado_cierre
    op.create_table(
        'ing_habilitado_cierre',
        sa.Column('id',                  sa.Integer(),    nullable=False),
        sa.Column('of_numero',           sa.String(50),   nullable=False),
        sa.Column('fecha',               sa.Date(),       nullable=False),
        sa.Column('turno',               sa.String(20),   nullable=False),
        sa.Column('supervisor',          sa.String(100),  nullable=False),
        sa.Column('prendas_cortadas',    sa.Integer(),    nullable=False),
        sa.Column('prendas_entregadas',  sa.Integer(),    nullable=False),
        sa.Column('kit_completo',        sa.String(50),   nullable=False),
        sa.Column('pct_entrega',         sa.Float(),      nullable=True),
        sa.Column('observacion',         sa.Text(),       nullable=True),
        sa.Column('created_at',          sa.DateTime(),   server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_habilitado_cierre_id',   'ing_habilitado_cierre', ['id'])
    op.create_index('ix_ing_hab_of_fecha',           'ing_habilitado_cierre', ['of_numero', 'fecha'])

    # 9. ing_ishikawa_causas
    op.create_table(
        'ing_ishikawa_causas',
        sa.Column('id',           sa.Integer(),  nullable=False),
        sa.Column('categoria',    sa.String(50), nullable=False),
        sa.Column('causa_texto',  sa.Text(),     nullable=False),
        sa.Column('porques_json', sa.Text(),     nullable=True),
        sa.Column('causa_raiz',   sa.Text(),     nullable=True),
        sa.Column('validada',     sa.Boolean(),  nullable=True, server_default='0'),
        sa.Column('created_at',   sa.DateTime(), server_default=sa.text('GETDATE()')),
        sa.Column('updated_at',   sa.DateTime(), server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ing_ishikawa_causas_id',     'ing_ishikawa_causas', ['id'])
    op.create_index('ix_ing_ishi_cat_validada',      'ing_ishikawa_causas', ['categoria', 'validada'])


def downgrade() -> None:
    op.drop_table('ing_ishikawa_causas')
    op.drop_table('ing_habilitado_cierre')
    op.drop_table('ing_fusionado_params')
    op.drop_table('ing_ole_diario')
    op.drop_table('ing_calidad_inspeccion')
    op.drop_table('ing_tendido_fichas')
    op.drop_table('ing_muestreo_obs')
    op.drop_table('ing_paradas_registro')
    op.drop_table('ing_sam_registros')
