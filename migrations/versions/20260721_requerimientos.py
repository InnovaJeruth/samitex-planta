"""Requerimientos comerciales (Muestra/Producción/Stock) — Fase 1, aditivo.

Crea 3 tablas nuevas. No toca ninguna tabla existente. Idempotente.

Revision ID: 20260721_requerimientos
Revises: 20260720_fk_indices
"""
from alembic import op
import sqlalchemy as sa

revision = "20260721_requerimientos"
down_revision = "20260720_fk_indices"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if "requerimientos" not in tablas:
        op.create_table(
            "requerimientos",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("numero_req", sa.String(40), nullable=False),
            sa.Column("tipo", sa.String(15), nullable=False, server_default="PRODUCCION"),
            sa.Column("cliente", sa.String(200), nullable=False),
            sa.Column("proceso", sa.String(60)),
            sa.Column("licitacion", sa.String(150)),
            sa.Column("fecha_solicitud", sa.Date),
            sa.Column("fecha_apt", sa.Date),
            sa.Column("ejecutivo", sa.String(120)),
            sa.Column("fecha_absolucion", sa.Date),
            sa.Column("nota", sa.Text),
            sa.Column("estado", sa.String(15), nullable=False, server_default="BORRADOR"),
            sa.Column("creado_por_id", sa.Integer, sa.ForeignKey("usuarios.id")),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_requerimientos_numero_req", "requerimientos",
                        ["numero_req"], unique=True)

    if "requerimiento_lineas" not in tablas:
        op.create_table(
            "requerimiento_lineas",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("requerimiento_id", sa.Integer,
                      sa.ForeignKey("requerimientos.id", ondelete="CASCADE"), nullable=False),
            sa.Column("grupo", sa.String(60)),
            sa.Column("item_num", sa.String(20)),
            sa.Column("sub_item", sa.String(20)),
            sa.Column("articulo", sa.String(60)),
            sa.Column("descripcion", sa.String(200), nullable=False),
            sa.Column("composicion", sa.String(200)),
            sa.Column("proveedor_tela", sa.String(120)),
            sa.Column("codigo_tela", sa.String(60)),
            sa.Column("color", sa.String(60)),
            sa.Column("tallaje", sa.String(1), nullable=False, server_default="C"),
            sa.Column("total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("prenda_catalogo_id", sa.Integer, sa.ForeignKey("prendas_catalogo.id")),
            sa.Column("orden", sa.Integer, nullable=False, server_default="0"),
        )
        op.create_index("ix_requerimiento_lineas_req", "requerimiento_lineas",
                        ["requerimiento_id"])

    if "requerimiento_linea_tallas" not in tablas:
        op.create_table(
            "requerimiento_linea_tallas",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("linea_id", sa.Integer,
                      sa.ForeignKey("requerimiento_lineas.id", ondelete="CASCADE"), nullable=False),
            sa.Column("talla", sa.String(20), nullable=False),
            sa.Column("cantidad", sa.Integer, nullable=False, server_default="0"),
        )
        op.create_index("ix_req_linea_tallas_linea", "requerimiento_linea_tallas",
                        ["linea_id"])


def downgrade():
    for tbl in ("requerimiento_linea_tallas", "requerimiento_lineas", "requerimientos"):
        op.drop_table(tbl)
