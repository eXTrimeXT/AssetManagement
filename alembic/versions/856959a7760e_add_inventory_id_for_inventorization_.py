"""add inventory_id for inventorization_items

Revision ID: 856959a7760e
Revises: 2893ce41900e
Create Date: 2026-09-15 14:44:39.756983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '856959a7760e'
down_revision: Union[str, Sequence[str], None] = '2893ce41900e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inventorization_items', sa.Column('inventory_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    pass
