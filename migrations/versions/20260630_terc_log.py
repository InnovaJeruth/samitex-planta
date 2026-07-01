"""add terc_subproceso_log and fase_id to terc_recepciones

Revision ID: 20260630_terc_log
Revises: 20260630_fase_terc
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260630_terc_log"
down_revision = "20260630_fase_terc"
branch_labels = None
depends_on = None


def upgrade():
    # Agregar fase_id a terc_recepciones (nullable, retrocompatible)
    op.add_column(
        "terc_recepciones",
        sa.Column("fase_id", sa.String(5), nullable=True),
    )

    # Nueva tabla ciclo de vida tercerización
    op.create_table(
        "terc_subproceso_log",
        sa.Column("id",                   sa.Integer,     primary_key=True),
        sa.Column("of_id",                sa.Integer,     sa.ForeignKey("ordenes_fabricacion.id"), nullable=False),
        sa.Column("planta_id",            sa.Integer,     sa.ForeignKey("plantas_externas.id"),    nullable=False),
        sa.Column("fase_id",              sa.String(5),   nullable=True),
        sa.Column("estado",               sa.String(20),  nullable=False, server_default="PROGRAMADO"),
        sa.Column("juegos_enviados",      sa.Integer,     nullable=True),
        sa.Column("juegos_recibidos",     sa.Integer,     nullable=True),
        sa.Column("fecha_programado",     sa.DateTime,    server_default=sa.func.now()),
        sa.Column("fecha_envio",          sa.Date,        nullable=True),
        sa.Column("fecha_recepcion_est",  sa.Date,        nullable=True),
        sa.Column("fecha_recepcion_real", sa.Date,        nullable=True),
        sa.Column("fecha_completado",     sa.DateTime,    nullable=True),
        sa.Column("observacion",          sa.Text,        nullable=True),
        sa.Column("usuario_creo_id",      sa.Integer,     sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("usuario_envio_id",     sa.Integer,     sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("usuario_recepcion_id", sa.Integer,     sa.ForeignKey("usuarios.id"), nullable=True),
    )


def downgrade():
    op.drop_table("terc_subproceso_log")
    op.drop_column("terc_recepciones", "fase_id")
