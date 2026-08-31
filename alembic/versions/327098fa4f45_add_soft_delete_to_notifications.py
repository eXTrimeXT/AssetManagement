"""add_soft_delete_to_notifications

Revision ID: 327098fa4f45
Revises: e159a4494bbc
Create Date: 2026-08-31 12:41:14.490782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '327098fa4f45'
down_revision: Union[str, Sequence[str], None] = 'e159a4494bbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('notifications', sa.Column('employee_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('notifications', sa.Column('initiator_deleted', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    op.drop_column('notifications', 'initiator_deleted')
    op.drop_column('notifications', 'employee_deleted')
