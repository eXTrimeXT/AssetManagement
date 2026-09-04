"""add dates to inventorization_sessions

Revision ID: d897b68253d6
Revises: 22ff88879585
Create Date: 2026-09-04 10:56:04.659475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd897b68253d6'
down_revision: Union[str, Sequence[str], None] = 'fc474f474d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('inventorization_sessions', sa.Column('start_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('inventorization_sessions', sa.Column('end_date', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('inventorization_sessions', 'end_date')
    op.drop_column('inventorization_sessions', 'start_date')
