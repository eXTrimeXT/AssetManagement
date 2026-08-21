"""change Notifications

Revision ID: cefd2405c3c9
Revises: 293f7efce7e0
Create Date: 2026-08-21 15:42:49.483422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cefd2405c3c9'
down_revision: Union[str, Sequence[str], None] = '293f7efce7e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Удаляем старый столбец
    op.drop_column('notifications', 'notification_checked')

    # Добавляем новые столбцы
    op.add_column('notifications', sa.Column(
        'event_type', sa.String(50), nullable=False, server_default='service_due'
    ))
    op.add_column('notifications', sa.Column(
        'initiator_id', sa.String(20), sa.ForeignKey('zup_employees.employee_id'), nullable=True
    ))
    op.add_column('notifications', sa.Column(
        'status', sa.String(20), nullable=False, server_default='unread'
    ))
    op.add_column('notifications', sa.Column(
        'responded_at', sa.DateTime(timezone=True), nullable=True
    ))

    # Индексы
    op.create_index('ix_notifications_event_type', 'notifications', ['event_type'])
    op.create_index('ix_notifications_status', 'notifications', ['status'])
    op.create_index('ix_notifications_employee_status', 'notifications', ['employee_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_notifications_employee_status', table_name='notifications')
    op.drop_index('ix_notifications_status', table_name='notifications')
    op.drop_index('ix_notifications_event_type', table_name='notifications')
    op.drop_column('notifications', 'responded_at')
    op.drop_column('notifications', 'status')
    op.drop_column('notifications', 'initiator_id')
    op.drop_column('notifications', 'event_type')
    op.add_column('notifications', sa.Column(
        'notification_checked', sa.Boolean(), nullable=False, server_default=sa.text('false')
    ))