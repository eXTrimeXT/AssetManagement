"""fix_asset_assignment_unique_constraint

Revision ID: c6b819793f81
Revises: 2ff504afbefc
Create Date: 2026-09-07 16:10:50.246037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6b819793f81'
down_revision: Union[str, Sequence[str], None] = '2ff504afbefc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Удаляем старый ошибочный констрейнт, который включает end_date
    op.drop_constraint('uq_asset_employee_type_active', 'asset_assignments', type_='unique')

    # 2. Создаем правильный ЧАСТИЧНЫЙ уникальный индекс (Partial Unique Index)
    # Он гарантирует, что у одного сотрудника может быть только ОДНА активная (end_date IS NULL)
    # привязка к конкретному активу и типу.
    # При этом исторические записи с одинаковыми end_date больше не будут вызывать ошибку.
    op.execute("""
               CREATE UNIQUE INDEX uq_active_asset_assignment
                   ON asset_assignments (asset_id, employee_id, assignment_type)
                   WHERE end_date IS NULL;
               """)


def downgrade() -> None:
    # Откат: удаляем правильный индекс
    op.execute("DROP INDEX IF EXISTS uq_active_asset_assignment;")

    # Откат: возвращаем старый (ошибочный) констрейнт
    op.create_unique_constraint(
        'uq_asset_employee_type_active',
        'asset_assignments',
        ['asset_id', 'employee_id', 'assignment_type', 'end_date']
    )
