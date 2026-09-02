"""add is_primary to asset_assignments

Revision ID: e063e05c83ca
Revises: 327098fa4f45
Create Date: 2026-09-02 14:33:50.378627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e063e05c83ca'
down_revision: Union[str, Sequence[str], None] = '327098fa4f45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_assignments', sa.Column('is_current', sa.Boolean(), nullable=True, default=False))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_assignments', 'is_current')
