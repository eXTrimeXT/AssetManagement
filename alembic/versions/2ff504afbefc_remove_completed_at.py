"""remove completed_at

Revision ID: 2ff504afbefc
Revises: d897b68253d6
Create Date: 2026-09-04 11:11:22.402266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ff504afbefc'
down_revision: Union[str, Sequence[str], None] = 'd897b68253d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('inventorization_sessions', 'completed_at')


def downgrade() -> None:
    op.add_column('inventorization_sessions', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

