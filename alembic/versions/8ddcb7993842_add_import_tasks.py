"""add import_tasks

Revision ID: 8ddcb7993842
Revises: 4f23a30c9188
Create Date: 2026-10-05 09:56:27.769691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ddcb7993842'
down_revision: Union[str, Sequence[str], None] = '4f23a30c9188'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('import_tasks', sa.Column('allowed_cost_centers', sa.JSON, nullable=True))
    op.add_column('import_tasks', sa.Column('items_data', sa.JSON, nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('import_tasks','allowed_cost_centers')
    op.drop_column('import_tasks','items_data')