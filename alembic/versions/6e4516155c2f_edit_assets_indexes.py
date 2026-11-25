"""edit Assets indexes

Revision ID: 6e4516155c2f
Revises: 8e9a99545e13
Create Date: 2026-11-25 12:01:38.943120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e4516155c2f'
down_revision: Union[str, Sequence[str], None] = '8e9a99545e13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ==================================================================
    # ШАГ 1: Очистка дубликатов перед созданием уникальных индексов
    # ==================================================================
    # Удаляем дубликаты по inventory_id (оставляем запись с максимальным asset_id)
    op.execute("""
               DELETE FROM assets
               WHERE asset_id NOT IN (
                   SELECT MAX(asset_id)
                   FROM assets
                   WHERE inventory_id IS NOT NULL
                   GROUP BY inventory_id
               )
                 AND inventory_id IS NOT NULL
                 AND inventory_id IN (
                   SELECT inventory_id
                   FROM assets
                   WHERE inventory_id IS NOT NULL
                   GROUP BY inventory_id
                   HAVING COUNT(*) > 1
               )
               """)

    # Удаляем дубликаты по material_id (оставляем запись с максимальным asset_id)
    op.execute("""
               DELETE FROM assets
               WHERE asset_id NOT IN (
                   SELECT MAX(asset_id)
                   FROM assets
                   WHERE material_id IS NOT NULL
                   GROUP BY material_id
               )
                 AND material_id IS NOT NULL
                 AND material_id IN (
                   SELECT material_id
                   FROM assets
                   WHERE material_id IS NOT NULL
                   GROUP BY material_id
                   HAVING COUNT(*) > 1
               )
               """)

    # ==================================================================
    # ШАГ 2: Удаление старых стандартных уникальных индексов (если есть)
    # ==================================================================
    # Стандартный уникальный индекс на material_id (создан из-за unique=True в колонке)
    op.execute("DROP INDEX IF EXISTS assets_material_id_key")

    # Стандартный уникальный индекс на inventory_id (если был создан ранее)
    op.execute("DROP INDEX IF EXISTS assets_inventory_id_key")

    # ==================================================================
    # ШАГ 3: Создание частичных уникальных индексов (IS NOT NULL)
    # ==================================================================
    # Частичный уникальный индекс для inventory_id
    op.create_index(
        'uq_assets_inventory_id',
        'assets',
        ['inventory_id'],
        unique=True,
        postgresql_where=sa.text('inventory_id IS NOT NULL')
    )

    # Частичный уникальный индекс для material_id
    op.create_index(
        'uq_assets_material_id',
        'assets',
        ['material_id'],
        unique=True,
        postgresql_where=sa.text('material_id IS NOT NULL')
    )


def downgrade() -> None:
    # Удаляем частичные уникальные индексы
    op.drop_index('uq_assets_material_id', table_name='assets')
    op.drop_index('uq_assets_inventory_id', table_name='assets')

    # Восстанавливаем старые стандартные уникальные индексы (если они были)
    op.create_index('assets_material_id_key', 'assets', ['material_id'], unique=True)
    op.create_index('assets_inventory_id_key', 'assets', ['inventory_id'], unique=True)
