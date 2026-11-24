"""edit InventorizationSession, add department_codes

Revision ID: b0c2d71633e8
Revises: 51d766776814
Create Date: 2026-10-05 14:57:09.083086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0c2d71633e8'
down_revision: Union[str, Sequence[str], None] = '51d766776814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем новое поле department_codes
    op.add_column('inventorization_sessions', sa.Column('department_codes', sa.String(length=500), nullable=True))

    # Делаем asset_type_id необязательным (nullable=True), так как сессия может быть создана только по департаментам
    op.alter_column('inventorization_sessions', 'asset_type_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    # Делаем текстовые поля типа актива необязательными
    op.alter_column('inventorization_sessions', 'asset_type_name',
                    existing_type=sa.String(length=100),
                    nullable=True)

    op.alter_column('inventorization_sessions', 'asset_type_en_name',
                    existing_type=sa.String(length=100),
                    nullable=True)


def downgrade() -> None:
    # Откат изменений в обратном порядке
    # Возвращаем обязательность полей типа актива
    op.alter_column('inventorization_sessions', 'asset_type_en_name',
                    existing_type=sa.String(length=100),
                    nullable=False)

    op.alter_column('inventorization_sessions', 'asset_type_name',
                    existing_type=sa.String(length=100),
                    nullable=False)

    op.alter_column('inventorization_sessions', 'asset_type_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # Удаляем новое поле
    op.drop_column('inventorization_sessions', 'department_codes')
