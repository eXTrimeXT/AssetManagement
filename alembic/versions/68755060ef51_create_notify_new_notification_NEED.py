"""create notify_new_notification()

Revision ID: 68755060ef51
Revises: cefd2405c3c9
Create Date: 2026-08-25 14:17:05.605188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '68755060ef51'
down_revision: Union[str, Sequence[str], None] = 'cefd2405c3c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Создаем функцию, которая отправляет уведомление
    op.execute("""
               CREATE OR REPLACE FUNCTION notify_new_notification()
                   RETURNS TRIGGER AS $$
               BEGIN
                   -- Отправляем событие в канал 'notification_channel' с данными новой строки в формате JSON
                   PERFORM pg_notify('notification_channel', row_to_json(NEW)::text);
                   RETURN NEW;
               END;
               $$ LANGUAGE plpgsql;
               """)

    # Привязываем функцию к таблице notifications
    op.execute("""
               CREATE TRIGGER trigger_new_notification
                   AFTER INSERT ON notifications
                   FOR EACH ROW EXECUTE FUNCTION notify_new_notification();
               """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trigger_new_notification ON notifications;")
    op.execute("DROP FUNCTION IF EXISTS notify_new_notification;")
