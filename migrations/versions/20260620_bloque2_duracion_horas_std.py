"""Bloque 2: agregar duracion_horas_std a fases_catalogo

Revision ID: bloque2_duracion_horas
Revises: be2d59390f04
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'bloque2_duracion_horas'
down_revision = 'be2d59390f04'
branch_labels = None
depends_on = None

# Duración estándar por fase (en horas), usada para auto-calcular
# inicio_programado al asignar fecha_inicio_plan en el Gantt.
# Estos son defaults ajustables por el planeador en la BD directamente.
DURACIONES = {
    'F1': 4.0,   # Tizado       — medio día
    'F2': 8.0,   # Tendido      — 1 día
    'F3': 6.0,   # Corte        — ¾ día
    'F4': 4.0,   # Numerado     — medio día
    'F8': 8.0,   # Estampado    — 1 día (tercerizable)
    'F9': 4.0,   # Auditoría    — medio día
    'F5': 6.0,   # Fusionado    — ¾ día
    'F6': 4.0,   # Calidad      — medio día
    'F7': 8.0,   # Habilitado   — 1 día
}


def upgrade():
    op.add_column(
        'fases_catalogo',
        sa.Column('duracion_horas_std', sa.Float(), nullable=True, server_default='8.0'),
    )
    # Setear duraciones específicas por fase
    conn = op.get_bind()
    for fase_id, horas in DURACIONES.items():
        conn.execute(
            sa.text(
                "UPDATE fases_catalogo SET duracion_horas_std = :h WHERE fase_id = :f"
            ),
            {'h': horas, 'f': fase_id},
        )


def downgrade():
    op.drop_column('fases_catalogo', 'duracion_horas_std')
