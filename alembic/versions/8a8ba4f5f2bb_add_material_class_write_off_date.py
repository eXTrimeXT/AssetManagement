"""add material_class, write_off_date

Revision ID: 8a8ba4f5f2bb
Revises: 2d8c30c9a1b7
Create Date: 2026-11-10 11:01:20.573367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8a8ba4f5f2bb'
down_revision: Union[str, Sequence[str], None] = '2d8c30c9a1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('assets', sa.Column('material_class', sa.String, nullable=True))
    op.add_column('assets', sa.Column('write_off_date', sa.String, nullable=True))



def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assets','material_class')
    op.drop_column('assets','write_off_date')

