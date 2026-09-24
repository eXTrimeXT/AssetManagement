"""add ccc_f & ccc

Revision ID: aed3518c1c6d
Revises: e59b38c56101
Create Date: 2026-09-24 15:03:03.604635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aed3518c1c6d'
down_revision: Union[str, Sequence[str], None] = 'e59b38c56101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('cost_center_code_from', sa.String(20), nullable=True))
    op.add_column('assets', sa.Column('cost_center_code', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('assets', 'cost_center_code_from')
    op.drop_column('assets', 'cost_center_code')
