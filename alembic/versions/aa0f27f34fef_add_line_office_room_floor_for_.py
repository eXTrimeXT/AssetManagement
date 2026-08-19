"""add line, office, room, floor for AssetPosition

Revision ID: aa0f27f34fef
Revises: d38ff63167a6
Create Date: 2026-08-19 09:42:16.267061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'aa0f27f34fef'
down_revision: Union[str, Sequence[str], None] = 'd38ff63167a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_positions', sa.Column('line', sa.String(length=100), nullable=True))
    op.add_column('asset_positions', sa.Column('office', sa.String(length=200), nullable=True))
    op.add_column('asset_positions', sa.Column('room', sa.String(length=200), nullable=True))
    op.add_column('asset_positions', sa.Column('floor', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_positions', 'floor')
    op.drop_column('asset_positions', 'room')
    op.drop_column('asset_positions', 'office')
    op.drop_column('asset_positions', 'line')