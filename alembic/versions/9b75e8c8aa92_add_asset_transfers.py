"""add asset_transfers

Revision ID: 9b75e8c8aa92
Revises: 6bee7c5e81f2
Create Date: 2026-09-22 11:33:16.328517

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# revision: str = '9b75e8c8aa92'
# down_revision: Union[str, Sequence[str], None] = '6bee7c5e81f2'
# branch_labels: Union[str, Sequence[str], None] = None
# depends_on: Union[str, Sequence[str], None] = None
#
#
# def upgrade() -> None:
#     op.create_table(
#         'asset_transfers',
#         sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
#         sa.Column('asset_id', sa.Integer(), nullable=False),
#         sa.Column('initiator_id', sa.String(length=10), nullable=False),
#         sa.Column('target_employee_id', sa.String(length=10), nullable=False),
#         sa.Column('assignment_type', sa.String(length=20), nullable=False),
#         sa.Column('status', sa.String(length=20), nullable=False),
#         sa.Column('initiator_comment', sa.Text(), nullable=True),
#         sa.Column('responder_comment', sa.Text(), nullable=True),
#         sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
#         sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
#         sa.ForeignKeyConstraint(['asset_id'], ['assets.asset_id'], ),
#         sa.ForeignKeyConstraint(['initiator_id'], ['zup_employees.employee_id'], ),
#         sa.ForeignKeyConstraint(['target_employee_id'], ['zup_employees.employee_id'], ),
#         sa.PrimaryKeyConstraint('id')
#     )
#     op.create_index('ix_asset_transfers_target_status', 'asset_transfers', ['target_employee_id', 'status'])
#     op.create_index('ix_asset_transfers_initiator', 'asset_transfers', ['initiator_id'])
#
# def downgrade() -> None:
#     op.drop_index('ix_asset_transfers_initiator', table_name='asset_transfers')
#     op.drop_index('ix_asset_transfers_target_status', table_name='asset_transfers')
#     op.drop_table('asset_transfers')