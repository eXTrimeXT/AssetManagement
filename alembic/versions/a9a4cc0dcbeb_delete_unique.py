"""delete unique

Revision ID: a9a4cc0dcbeb
Revises: c6b819793f81
Create Date: 2026-09-08 14:23:38.662307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9a4cc0dcbeb'
down_revision: Union[str, Sequence[str], None] = 'c6b819793f81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # op.drop_constraint('uq_assets_inventory_id', 'assets', type_='unique')
    # op.drop_constraint('uq_assets_serial_number', 'assets', type_='unique')

    # ПРИМЕЧАНИЕ: Если в вашей БД они были созданы именно как уникальные индексы (с префиксом ix_),
    # закомментируйте строки выше и раскомментируйте эти:
    op.drop_index('ix_assets_inventory_id', table_name='assets')
    op.drop_index('ix_assets_serial_number', table_name='assets')

    # Если Postgres создал их со стандартным суффиксом _key, используйте:
    # op.drop_constraint('assets_inventory_id_key', 'assets', type_='unique')
    # op.drop_constraint('assets_serial_number_key', 'assets', type_='unique')


def downgrade() -> None:
    # Восстанавливаем уникальные ограничения при откате миграции
    op.create_unique_constraint('uq_assets_inventory_id', 'assets', ['inventory_id'])
    op.create_unique_constraint('uq_assets_serial_number', 'assets', ['serial_number'])