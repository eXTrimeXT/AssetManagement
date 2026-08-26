"""create notify_notification_change

Revision ID: 260cdae63265
Revises: 68755060ef51
Create Date: 2026-08-26 09:47:42.606466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '260cdae63265'
down_revision: Union[str, Sequence[str], None] = '68755060ef51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Создаем функцию, которая отправляет уведомление при ЛЮБОМ изменении
    op.execute("""
               CREATE OR REPLACE FUNCTION notify_notification_change()
                   RETURNS TRIGGER AS $$
               DECLARE
                   target_employee_id text;
               BEGIN
                   -- Определяем, чьи уведомления изменились
                   IF (TG_OP = 'DELETE') THEN
                       target_employee_id := OLD.employee_id;
                   ELSE
                       target_employee_id := NEW.employee_id;
                   END IF;

                   -- Отправляем минимальный сигнал с ID сотрудника, чтобы разбудить SSE
                   PERFORM pg_notify(
                           'notification_channel',
                           json_build_object('employee_id', target_employee_id, 'action', TG_OP)::text
                           );

                   IF (TG_OP = 'DELETE') THEN
                       RETURN OLD;
                   ELSE
                       RETURN NEW;
                   END IF;
               END;
               $$ LANGUAGE plpgsql;
               """)

    # Привязываем функцию к INSERT, UPDATE и DELETE
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_new_notification ON notifications;
        
        CREATE TRIGGER trigger_notification_change
        AFTER INSERT OR UPDATE OR DELETE ON notifications
        FOR EACH ROW EXECUTE FUNCTION notify_notification_change();
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trigger_notification_change ON notifications;")
    op.execute("DROP FUNCTION IF EXISTS notify_notification_change;")