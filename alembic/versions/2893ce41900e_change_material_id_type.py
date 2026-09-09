"""change material_id type

Revision ID: 2893ce41900e
Revises: 374a4c4a7fd6
Create Date: 2026-09-09 16:56:37.389743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2893ce41900e'
down_revision: Union[str, Sequence[str], None] = '374a4c4a7fd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Меняем тип колонки с INTEGER на VARCHAR(50)
    op.alter_column(
        'assets',
        'material_id',
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=True
    )


def downgrade() -> None:
    # При откате меняем обратно на INTEGER (с явным приведением типов)
    op.alter_column(
        'assets',
        'material_id',
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='material_id::integer'
    )
