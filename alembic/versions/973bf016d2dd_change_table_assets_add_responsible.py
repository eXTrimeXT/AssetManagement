"""change table assets, add responsible

Revision ID: 973bf016d2dd
Revises: 4bd04094d764
Create Date: 2026-08-17 16:31:52.363658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '973bf016d2dd'
down_revision: Union[str, Sequence[str], None] = '4bd04094d764'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Добавляем поле assignment_type
    op.add_column('asset_assignments', sa.Column('assignment_type', sa.String(20), nullable=False, server_default='user'))
    op.create_index('ix_asset_assignments_assignment_type', 'asset_assignments', ['assignment_type'])

    # Удаляем старый constraint
    op.drop_constraint('uq_asset_employee_active', 'asset_assignments', type_='unique')

    # Создаем новый constraint с учетом типа
    op.create_unique_constraint(
        'uq_asset_employee_type_active',
        'asset_assignments',
        ['asset_id', 'employee_id', 'assignment_type', 'end_date']
    )

def downgrade() -> None:
    op.drop_constraint('uq_asset_employee_type_active', 'asset_assignments', type_='unique')
    op.create_unique_constraint('uq_asset_employee_active', 'asset_assignments', ['asset_id', 'employee_id', 'end_date'])
    op.drop_index('ix_asset_assignments_assignment_type', table_name='asset_assignments')
    op.drop_column('asset_assignments', 'assignment_type')
