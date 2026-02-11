"""remove inqry_div from data_sync_log

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # inqry_div 컬럼이 존재하는 경우에만 제거 (fresh DB에는 없음)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'data_sync_log' AND column_name = 'inqry_div'"
        )
    )
    if result.fetchone():
        op.drop_constraint('data_sync_log_pkey', 'data_sync_log', type_='primary')
        op.drop_column('data_sync_log', 'inqry_div')
        op.create_primary_key('data_sync_log_pkey', 'data_sync_log', ['sync_date'])


def downgrade() -> None:
    op.drop_constraint('data_sync_log_pkey', 'data_sync_log', type_='primary')
    op.add_column('data_sync_log', sa.Column('inqry_div', sa.String(1), server_default='1', nullable=False))
    op.create_primary_key('data_sync_log_pkey', 'data_sync_log', ['sync_date', 'inqry_div'])
