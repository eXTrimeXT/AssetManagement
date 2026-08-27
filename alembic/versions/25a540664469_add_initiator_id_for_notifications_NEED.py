"""add initiator_id for notifications

Revision ID: 25a540664469
Revises: 260cdae63265
Create Date: 2026-08-27 10:21:45.560318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25a540664469'
down_revision: Union[str, Sequence[str], None] = '260cdae63265'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Пересоздаём функцию триггера с добавлением initiator_id
    op.execute("""
               CREATE OR REPLACE FUNCTION notify_notification_change()
                   RETURNS TRIGGER AS $$
               BEGIN
                   -- Отправляем сигнал с обоими ID, чтобы менеджер мог разослать всем затронутым пользователям
                   PERFORM pg_notify(
                           'notification_channel',
                           json_build_object(
                                   'employee_id',  CASE WHEN TG_OP = 'DELETE' THEN OLD.employee_id  ELSE NEW.employee_id  END,
                                   'initiator_id', CASE WHEN TG_OP = 'DELETE' THEN OLD.initiator_id ELSE NEW.initiator_id END,
                                   'action', TG_OP
                           )::text
                           );

                   IF (TG_OP = 'DELETE') THEN
                       RETURN OLD;
                   ELSE
                       RETURN NEW;
                   END IF;
               END;
               $$ LANGUAGE plpgsql;
               """)

def downgrade():
    # Откат к предыдущей версии (только employee_id)
    op.execute("""
               CREATE OR REPLACE FUNCTION notify_notification_change()
                   RETURNS TRIGGER AS $$
               DECLARE
                   target_employee_id text;
               BEGIN
                   IF (TG_OP = 'DELETE') THEN
                       target_employee_id := OLD.employee_id;
                   ELSE
                       target_employee_id := NEW.employee_id;
                   END IF;

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
