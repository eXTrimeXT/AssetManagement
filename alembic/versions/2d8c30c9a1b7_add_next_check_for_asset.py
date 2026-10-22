"""add next_check for Asset

Revision ID: 2d8c30c9a1b7
Revises: 1a5010a764a2
Create Date: 2026-10-14 12:11:41.216557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d8c30c9a1b7'
down_revision: Union[str, Sequence[str], None] = '1a5010a764a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('assets', sa.Column('next_check', sa.Date, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assets','next_check')
