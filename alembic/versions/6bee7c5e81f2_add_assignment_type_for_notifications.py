"""add assignment_type for Notifications

Revision ID: 6bee7c5e81f2
Revises: 856959a7760e
Create Date: 2026-09-18 16:01:17.279442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6bee7c5e81f2'
down_revision: Union[str, Sequence[str], None] = '856959a7760e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('notifications', sa.Column('assignment_type', sa.String(length=20), nullable=True))

def downgrade() -> None:
    op.drop_column('notifications', 'assignment_type')
