"""edit InventorizationSession

Revision ID: e159a4494bbc
Revises: 25a540664469
Create Date: 2026-08-27 14:25:51.050436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e159a4494bbc'
down_revision: Union[str, Sequence[str], None] = '25a540664469'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # =========================================================
    # 1. Изменения в таблице notifications
    # =========================================================
    # Делаем asset_id необязательным (уведомление может быть о всей сессии, а не об одном активе)
    op.alter_column('notifications', 'asset_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)

    # Добавляем session_id для привязки к инвентаризации
    op.add_column('notifications', sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_notifications_session_id'), 'notifications', ['session_id'], unique=False)

    # =========================================================
    # 2. Изменения в таблице inventorization_sessions
    # =========================================================
    # Добавляем created_by (создатель сессии)
    op.add_column('inventorization_sessions', sa.Column('created_by', sa.String(20), nullable=True))

    # Создаем внешний ключ на таблицу сотрудников
    op.create_foreign_key(
        'fk_inv_session_created_by',
        'inventorization_sessions', 'zup_employees',
        ['created_by'], ['employee_id']
    )

    # Если у вас в БД уже есть старые записи инвентаризации и вы хотите сделать поле обязательным,
    # раскомментируйте строку ниже (предварительно проставив значения для старых строк):
    # op.alter_column('inventorization_sessions', 'created_by', nullable=False)

    # Добавляем completed_at (время завершения)
    op.add_column('inventorization_sessions', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Откат изменений в inventorization_sessions
    op.drop_column('inventorization_sessions', 'completed_at')
    op.drop_constraint('fk_inv_session_created_by', 'inventorization_sessions', type_='foreignkey')
    op.drop_column('inventorization_sessions', 'created_by')

    # Откат изменений в notifications
    op.drop_index(op.f('ix_notifications_session_id'), table_name='notifications')
    op.drop_column('notifications', 'session_id')
    op.alter_column('notifications', 'asset_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)
