"""add updated_at for asset_assignments

Revision ID: 8e9a99545e13
Revises: 12404f08b66e
Create Date: 2026-11-24 16:05:18.940275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8e9a99545e13'
down_revision: Union[str, Sequence[str], None] = '12404f08b66e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_assignments', sa.Column('updated_at', sa.DateTime, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_assignments','updated_at')

