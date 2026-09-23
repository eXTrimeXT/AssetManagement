"""add check_period

Revision ID: e59b38c56101
Revises: 9b75e8c8aa92
Create Date: 2026-09-23 08:53:45.128014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e59b38c56101'
down_revision: Union[str, Sequence[str], None] = '9b75e8c8aa92' # cut revision ?
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('check_period', sa.Integer(), nullable=False, server_default=sa.text('0')))


def downgrade() -> None:
    op.drop_column('assets', 'check_period')