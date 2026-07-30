"""Alembic env.py — Samitex Planta
Lee DATABASE_URL desde app.config.settings para evitar credenciales en texto plano.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Asegurar que el proyecto raíz esté en sys.path ──────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Config de Alembic ────────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Importar modelos para autogenerate ───────────────────────────
# Importar Base y TODOS los modelos para que Alembic los detecte
from app.database.connection import Base  # noqa: E402
import app.models.usuario   # noqa: F401
import app.models.of        # noqa: F401
import app.models.pieza     # noqa: F401
import app.models.fase      # noqa: F401
import app.models.planta    # noqa: F401
import app.models.catalogo  # noqa: F401
import app.models.curva_tallas  # noqa: F401
import app.models.ingenieria    # noqa: F401
import app.models.parametro     # noqa: F401
import app.models.trazo         # noqa: F401
import app.models.paquete       # noqa: F401

target_metadata = Base.metadata

# ── Inyectar URL desde settings ──────────────────────────────────
from app.config import settings  # noqa: E402
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Corre migraciones sin conexión activa (genera SQL puro)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Corre migraciones con conexión activa."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
