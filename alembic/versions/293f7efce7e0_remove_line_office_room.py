"""remove line, office, room

Revision ID: 293f7efce7e0
Revises: 32a90855374a
Create Date: 2026-08-21 11:51:54.784495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '293f7efce7e0'
down_revision: Union[str, Sequence[str], None] = '32a90855374a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_positions', sa.Column('place', sa.String(length=100), nullable=True))
    op.drop_column('asset_positions', 'line')
    op.drop_column('asset_positions', 'office')
    op.drop_column('asset_positions', 'room')
    op.drop_column('asset_positions', 'floor')
    op.add_column('asset_positions', sa.Column('floor', sa.Integer, nullable=True, default=0))


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('asset_positions', sa.Column('line', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.add_column('asset_positions', sa.Column('office', sa.VARCHAR(length=200), autoincrement=False, nullable=True))
    op.add_column('asset_positions', sa.Column('room', sa.VARCHAR(length=200), autoincrement=False, nullable=True))
    op.add_column('asset_positions', sa.Column('floor', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.drop_column('asset_positions', 'place')
