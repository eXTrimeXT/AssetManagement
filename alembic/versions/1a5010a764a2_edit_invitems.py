"""edit InvItems

Revision ID: 1a5010a764a2
Revises: b0c2d71633e8
Create Date: 2026-10-05 16:38:05.723474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a5010a764a2'
down_revision: Union[str, Sequence[str], None] = 'b0c2d71633e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Делаем asset_id необязательным
    op.alter_column('inventorization_items', 'asset_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    # Добавляем material_id
    op.add_column('inventorization_items', sa.Column('material_id', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_inventorization_items_material_id'), 'inventorization_items', ['material_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_inventorization_items_material_id'), table_name='inventorization_items')
    op.drop_column('inventorization_items', 'material_id')
    op.alter_column('inventorization_items', 'asset_id',
                    existing_type=sa.Integer(),
                    nullable=False)
