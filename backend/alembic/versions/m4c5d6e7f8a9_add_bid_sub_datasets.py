"""add bid sub datasets (incntv rgn, jntcontrct duty rgn, subsi cnstty, attachments)

Revision ID: m4c5d6e7f8a9
Revises: l3b4c5d6e7f8
Create Date: 2026-11-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'm4c5d6e7f8a9'
down_revision = 'l3b4c5d6e7f8'
branch_labels = None
depends_on = None


def _fetched_at() -> sa.Column:
    return sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        'bid_incntv_rgns',
        sa.Column('bid_ntce_no', sa.String(50), nullable=False),
        sa.Column('bid_ntce_ord', sa.String(10), nullable=False, server_default='000'),
        sa.Column('sno', sa.Integer(), nullable=False),
        sa.Column('incntv_rgn_nm', sa.String(200), nullable=True),
        sa.Column('ntce_ntice_dt', sa.String(30), nullable=True),
        _fetched_at(),
        sa.PrimaryKeyConstraint('bid_ntce_no', 'bid_ntce_ord', 'sno'),
    )
    op.create_index('ix_bid_incntv_rgns_incntv_rgn_nm', 'bid_incntv_rgns', ['incntv_rgn_nm'])

    op.create_table(
        'bid_jntcontrct_duty_rgns',
        sa.Column('bid_ntce_no', sa.String(50), nullable=False),
        sa.Column('bid_ntce_ord', sa.String(10), nullable=False, server_default='000'),
        sa.Column('sno', sa.Integer(), nullable=False),
        sa.Column('jntcontrct_duty_rgn_nm', sa.String(200), nullable=True),
        sa.Column('rgn_duty_jntcontrct_rt', sa.String(20), nullable=True),
        sa.Column('ntce_ntice_dt', sa.String(30), nullable=True),
        _fetched_at(),
        sa.PrimaryKeyConstraint('bid_ntce_no', 'bid_ntce_ord', 'sno'),
    )
    op.create_index(
        'ix_bid_jntcontrct_duty_rgns_jntcontrct_duty_rgn_nm',
        'bid_jntcontrct_duty_rgns',
        ['jntcontrct_duty_rgn_nm'],
    )

    op.create_table(
        'bid_subsi_cnsttys',
        sa.Column('bid_ntce_no', sa.String(50), nullable=False),
        sa.Column('bid_ntce_ord', sa.String(10), nullable=False, server_default='000'),
        sa.Column('sno', sa.Integer(), nullable=False),
        sa.Column('subsi_cnstty_cd', sa.String(20), nullable=True),
        sa.Column('subsi_cnstty_nm', sa.String(300), nullable=True),
        sa.Column('subsi_cnstty_indstryty_evl_rt', sa.String(20), nullable=True),
        sa.Column('ntce_ntice_dt', sa.String(30), nullable=True),
        _fetched_at(),
        sa.PrimaryKeyConstraint('bid_ntce_no', 'bid_ntce_ord', 'sno'),
    )
    op.create_index('ix_bid_subsi_cnsttys_subsi_cnstty_nm', 'bid_subsi_cnsttys', ['subsi_cnstty_nm'])

    op.create_table(
        'bid_attachments',
        sa.Column('bid_ntce_no', sa.String(50), nullable=False),
        sa.Column('bid_ntce_ord', sa.String(10), nullable=False, server_default='000'),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False, server_default='api'),
        _fetched_at(),
        sa.PrimaryKeyConstraint('bid_ntce_no', 'bid_ntce_ord'),
    )

    op.add_column(
        'data_sync_log',
        sa.Column('sub_datasets_synced', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # 알림 중복 방지용 최초 삽입 시각. 기존 행은 마이그레이션 시각으로 채워진다
    # (알림 스케줄러가 rgst_dt 하한으로 일회성 폭주를 제한한다).
    op.add_column(
        'bid_notices',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index('ix_bid_notices_created_at', 'bid_notices', ['created_at'])
    op.add_column('data_sync_log', sa.Column('total_incntv_rgns', sa.Integer(), server_default='0'))
    op.add_column('data_sync_log', sa.Column('total_jntcontrct_duty_rgns', sa.Integer(), server_default='0'))
    op.add_column('data_sync_log', sa.Column('total_subsi_cnsttys', sa.Integer(), server_default='0'))


def downgrade() -> None:
    op.drop_index('ix_bid_notices_created_at', table_name='bid_notices')
    op.drop_column('bid_notices', 'created_at')
    op.drop_column('data_sync_log', 'sub_datasets_synced')
    op.drop_column('data_sync_log', 'total_subsi_cnsttys')
    op.drop_column('data_sync_log', 'total_jntcontrct_duty_rgns')
    op.drop_column('data_sync_log', 'total_incntv_rgns')
    op.drop_table('bid_attachments')
    op.drop_index('ix_bid_subsi_cnsttys_subsi_cnstty_nm', table_name='bid_subsi_cnsttys')
    op.drop_table('bid_subsi_cnsttys')
    op.drop_index(
        'ix_bid_jntcontrct_duty_rgns_jntcontrct_duty_rgn_nm',
        table_name='bid_jntcontrct_duty_rgns',
    )
    op.drop_table('bid_jntcontrct_duty_rgns')
    op.drop_index('ix_bid_incntv_rgns_incntv_rgn_nm', table_name='bid_incntv_rgns')
    op.drop_table('bid_incntv_rgns')
