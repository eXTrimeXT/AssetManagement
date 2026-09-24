"""add ccc_name shortname, from_name, from_shortname

Revision ID: 925555c2bc4f
Revises: aed3518c1c6d
Create Date: 2026-09-24 15:50:01.068126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '925555c2bc4f'
down_revision: Union[str, Sequence[str], None] = 'aed3518c1c6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('cost_center_name_from', sa.String(50), nullable=True))
    op.add_column('assets', sa.Column('cost_center_shortname_from', sa.String(12), nullable=True))

    op.add_column('assets', sa.Column('cost_center_name', sa.String(50), nullable=True))
    op.add_column('assets', sa.Column('cost_center_shortname', sa.String(12), nullable=True))

def downgrade() -> None:
    op.drop_column('assets', 'cost_center_name_from')
    op.drop_column('assets', 'cost_center_shortname_from')

    op.drop_column('assets', 'cost_center_name')
    op.drop_column('assets', 'cost_center_shortname')
