"""add license limits table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-10 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bid_license_limits',
        sa.Column('bid_ntce_no', sa.String(50), nullable=False),
        sa.Column('bid_ntce_ord', sa.String(10), nullable=False, server_default='000'),
        sa.Column('lmt_grp_no', sa.String(10), nullable=False),
        sa.Column('lmt_sno', sa.String(10), nullable=False),
        sa.Column('lcns_lmt_nm', sa.String(500), nullable=True),
        sa.Column('permsn_indstryty_list', sa.Text(), nullable=True),
        sa.Column('bsns_div_nm', sa.String(30), nullable=True),
        sa.Column('rgst_dt', sa.String(30), nullable=True),
        sa.Column('indstryty_mfrc_fld_list', sa.Text(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('bid_ntce_no', 'bid_ntce_ord', 'lmt_grp_no', 'lmt_sno'),
    )
    op.create_index(
        'ix_bid_license_limits_permsn_indstryty_list',
        'bid_license_limits',
        ['permsn_indstryty_list'],
    )

    op.add_column(
        'data_sync_log',
        sa.Column('total_license_limits', sa.Integer(), server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('data_sync_log', 'total_license_limits')
    op.drop_index('ix_bid_license_limits_permsn_indstryty_list', table_name='bid_license_limits')
    op.drop_table('bid_license_limits')
