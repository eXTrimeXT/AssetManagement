"""add checked_by for inventorization items

Revision ID: 6e6ef42b603a
Revises: 925555c2bc4f
Create Date: 2026-09-29 13:17:38.876702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e6ef42b603a'
down_revision: Union[str, Sequence[str], None] = '925555c2bc4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inventorization_items', sa.Column('checked_by', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('inventorization_items', 'checked_by')
