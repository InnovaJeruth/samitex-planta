"""Calidad/Reprocesos: motivos_rechazo (catálogo CR) + of_paquete_rechazos

Aditivo. No toca of_paquetes ni sus estados (eso va con el servicio de calidad).
Siembra los 53 defectos de corte de los formatos FR-GC-CR-001/002/003.

Revision ID: 20260714_calidad_rechazos
Revises: 20260710_paquetes
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = '20260714_calidad_rechazos'
down_revision = '20260710_paquetes'
branch_labels = None
depends_on = None


DEFECTOS = [
    ("CR01", "ANGULO CURVO"), ("CR02", "ANGULO ASIMETRICO"), ("CR03", "ANGULO FUERA DE MEDIDA"),
    ("CR04", "CORTE INCOMPLETO"), ("CR05", "CORTE INCORRECTO"), ("CR06", "DESALINEADO"),
    ("CR07", "DESCASADO"), ("CR08", "DESHERMANADO"), ("CR09", "ENSANCHE INCORRECTO"),
    ("CR10", "ENTRETELA INCORRECTA"), ("CR11", "ESCALADO INCORRECTO"), ("CR12", "FUSIONADO MAL AFINADO"),
    ("CR13", "HUECO"), ("CR14", "MAL APLOMADO"), ("CR15", "MAL BLOQUEADO"), ("CR16", "MAL CAMBIO DE PIEZA"),
    ("CR17", "MAL EMPALME"), ("CR18", "MAL ENUMERADO"), ("CR19", "MAL HABILITADO"), ("CR20", "MAL REBAJE"),
    ("CR21", "MAL TENDIDO"), ("CR22", "MANCHAS (ORIGEN CORTE)"), ("CR23", "MARCAS DE GOMA"),
    ("CR24", "MARGEN INCORRECTO"), ("CR25", "MATCHING INCORRECTO"), ("CR26", "MEDIDA INCORRECTA x MAL CORTE"),
    ("CR27", "MEDIDA INCORRECTA x MOLDE EQUIV."), ("CR28", "MOLDE INCORRECTO"), ("CR29", "PIEZA ASIMETRICA"),
    ("CR30", "PIEZA DEFORME"), ("CR31", "PIEZA FALTANTE"), ("CR32", "PIEZA INCORRECTA"),
    ("CR33", "PIEZA MAL FUSIONADA"), ("CR34", "PIEZA SIN ENUMERAR"), ("CR35", "PIEZA SIN FUSIONAR"),
    ("CR36", "PIEZAS CON ORILLO"), ("CR37", "PIQUETE FUERA DE MEDIDA"), ("CR38", "PIQUETE FUERA DE POSICION"),
    ("CR39", "PUNTO SUCIO"), ("CR40", "SENTIDO DE TELA INVERTIDO"), ("CR41", "SESGADO"),
    ("CR42", "SIN BLOQUEAR"), ("CR43", "SIN PERFORACION"), ("CR44", "SIN PIQUETE"), ("CR45", "SIN VARIANTE"),
    ("CR46", "SOPLADO"), ("CR47", "TAJO FUERA DE MEDIDA"), ("CR48", "TENDIDO TENSIONADO"),
    ("CR49", "TIZADO INCOMPLETO"), ("CR50", "TIZADO INCORRECTO"), ("CR51", "TIZADO MONTADO"),
    ("CR52", "TONO ENTRE PIEZAS"), ("CR53", "VARIANTE INCORRECTO"),
]


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if 'motivos_rechazo' not in tablas:
        op.create_table(
            'motivos_rechazo',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('codigo', sa.String(length=10), nullable=False),
            sa.Column('descripcion', sa.String(length=120), nullable=False),
            sa.Column('severidad', sa.String(length=10), nullable=True),
            sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.UniqueConstraint('codigo', name='uq_motivo_rechazo_codigo'),
        )

    if 'of_paquete_rechazos' not in tablas:
        op.create_table(
            'of_paquete_rechazos',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('paquete_id', sa.Integer(), sa.ForeignKey('of_paquetes.id', ondelete='CASCADE'), nullable=False),
            sa.Column('motivo_id', sa.Integer(), sa.ForeignKey('motivos_rechazo.id'), nullable=False),
            sa.Column('cantidad', sa.Integer(), nullable=False),
            sa.Column('tipo', sa.String(length=15), nullable=True),
            sa.Column('fase_destino', sa.String(length=10), nullable=True),
            sa.Column('estado', sa.String(length=15), nullable=False, server_default='PENDIENTE'),
            sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_of_paquete_rechazos_paquete', 'of_paquete_rechazos', ['paquete_id'])

    # Seed idempotente de los 53 defectos de corte
    motivos = sa.table(
        'motivos_rechazo',
        sa.column('codigo', sa.String),
        sa.column('descripcion', sa.String),
        sa.column('activo', sa.Boolean),
    )
    existentes = {r[0] for r in bind.execute(sa.text("SELECT codigo FROM motivos_rechazo")).fetchall()}
    faltantes = [{'codigo': c, 'descripcion': d, 'activo': True}
                 for (c, d) in DEFECTOS if c not in existentes]
    if faltantes:
        op.bulk_insert(motivos, faltantes)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'of_paquete_rechazos' in tablas:
        op.drop_index('ix_of_paquete_rechazos_paquete', table_name='of_paquete_rechazos')
        op.drop_table('of_paquete_rechazos')
    if 'motivos_rechazo' in tablas:
        op.drop_table('motivos_rechazo')
