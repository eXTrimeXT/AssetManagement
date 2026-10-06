"""add employee_id for ImportTask

Revision ID: 51d766776814
Revises: 8ddcb7993842
Create Date: 2026-10-05 11:13:55.304291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51d766776814'
down_revision: Union[str, Sequence[str], None] = '8ddcb7993842'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('import_tasks', sa.Column('employee_id', sa.String(20), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('import_tasks','employee_id')
