"""add notify_change_asset_status

Revision ID: fc474f474d02
Revises: e063e05c83ca
Create Date: 2026-09-02 16:26:48.108759

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fc474f474d02'
down_revision: Union[str, Sequence[str], None] = 'e063e05c83ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем триггерную функцию
    op.execute("""
               CREATE OR REPLACE FUNCTION notify_asset_status_change()
                   RETURNS TRIGGER AS $$
               BEGIN
                   -- Проверяем, изменился ли именно статус (IS DISTINCT FROM корректно работает с NULL)
                   IF OLD.asset_status_id IS DISTINCT FROM NEW.asset_status_id THEN

                       -- Массовая вставка уведомлений для всех активных привязок (user, responsible, serving)
                       INSERT INTO notifications (
                           employee_id,
                           initiator_id,
                           asset_id,
                           event_type,
                           status,
                           created_at
                       )
                       SELECT
                           aa.employee_id,
                           NEW.updated_by,          -- Тот, кто изменил статус
                           NEW.asset_id,
                           'asset_status_changed',  -- Тип события для фронтенда
                           'unread',
                           NOW()
                       FROM asset_assignments aa
                       WHERE aa.asset_id = NEW.asset_id
                         AND aa.end_date IS NULL;   -- Только активные связки

                       -- Оповещение канала для SSE (Server-Sent Events), если используется в main.py
                       PERFORM pg_notify('notification_channel', json_build_object(
                               'event', 'asset_status_changed',
                               'asset_id', NEW.asset_id
                                                                 )::text);

                   END IF;

                   RETURN NEW;
               END;
               $$ LANGUAGE plpgsql;
               """)

    # Создаем триггер, который срабатывает после UPDATE на таблице assets
    op.execute("""
               CREATE TRIGGER trigger_asset_status_change
                   AFTER UPDATE ON assets
                   FOR EACH ROW
               EXECUTE FUNCTION notify_asset_status_change();
               """)


def downgrade() -> None:
    # Удаляем триггер
    op.execute("DROP TRIGGER IF EXISTS trigger_asset_status_change ON assets;")
    # Удаляем функцию
    op.execute("DROP FUNCTION IF EXISTS notify_asset_status_change();")
