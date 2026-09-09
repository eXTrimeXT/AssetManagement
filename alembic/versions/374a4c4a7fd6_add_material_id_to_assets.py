"""add_material_id_to_assets

Revision ID: 374a4c4a7fd6
Revises: a9a4cc0dcbeb
Create Date: 2026-09-09 11:51:14.632837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '374a4c4a7fd6'
down_revision: Union[str, Sequence[str], None] = 'a9a4cc0dcbeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('material_id', sa.Integer(), nullable=True))
    op.create_index('ix_assets_material_id', 'assets', ['material_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_assets_material_id', table_name='assets')
    op.drop_column('assets', 'material_id')