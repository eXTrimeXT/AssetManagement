"""make_asset_position_fields_nullable

Revision ID: 4f23a30c9188
Revises: 6e6ef42b603a
Create Date: 2026-10-02 12:24:15.268278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f23a30c9188'
down_revision: Union[str, Sequence[str], None] = '6e6ef42b603a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Убираем ограничение NOT NULL для всех полей локации
    op.alter_column('asset_positions', 'workshop_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('asset_positions', 'place', existing_type=sa.String(), nullable=True)
    op.alter_column('asset_positions', 'level', existing_type=sa.Integer(), nullable=True)
    op.alter_column('asset_positions', 'x', existing_type=sa.Integer(), nullable=True)
    op.alter_column('asset_positions', 'y', existing_type=sa.Integer(), nullable=True)
    op.alter_column('asset_positions', 'rotation', existing_type=sa.Integer(), nullable=True)
    op.alter_column('asset_positions', 'scale', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Возвращаем ограничения NOT NULL (если потребуется откат)
    op.alter_column('asset_positions', 'workshop_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('asset_positions', 'place', existing_type=sa.String(), nullable=False)
    op.alter_column('asset_positions', 'level', existing_type=sa.Integer(), nullable=False)
    op.alter_column('asset_positions', 'x', existing_type=sa.Integer(), nullable=False)
    op.alter_column('asset_positions', 'y', existing_type=sa.Integer(), nullable=False)
    op.alter_column('asset_positions', 'rotation', existing_type=sa.Integer(), nullable=False)
    op.alter_column('asset_positions', 'scale', existing_type=sa.Integer(), nullable=False)