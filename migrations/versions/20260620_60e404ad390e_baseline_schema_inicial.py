"""baseline_schema_inicial

Revision ID: 60e404ad390e
Revises: 
Create Date: 2026-06-20 03:31:18.607966+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60e404ad390e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline: la BD ya existe con todas las tablas creadas via SQL scripts manuales.
    # Esta revisión marca el punto de partida para futuras migraciones con Alembic.
    # Desde aquí, usar: alembic revision --autogenerate -m "descripcion"
    pass


def downgrade() -> None:
    # No se puede revertir el baseline
    pass
