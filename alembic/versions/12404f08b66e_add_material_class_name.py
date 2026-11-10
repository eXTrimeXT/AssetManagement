"""add material_class_name

Revision ID: 12404f08b66e
Revises: 8a8ba4f5f2bb
Create Date: 2026-11-10 16:04:56.987363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12404f08b66e'
down_revision: Union[str, Sequence[str], None] = '8a8ba4f5f2bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('assets', sa.Column('material_class_name', sa.String, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assets','material_class_name')
