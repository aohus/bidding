"""add bid data tables

Revision ID: a1b2c3d4e5f6
Revises: 491ffb0fcb27
Create Date: 2026-02-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '491ffb0fcb27'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # bid_notices - 입찰공고 데이터
    op.create_table(
        'bid_notices',
        sa.Column('bid_ntce_no', sa.String(50), primary_key=True),
        sa.Column('bid_ntce_ord', sa.String(10), primary_key=True),
        sa.Column('rgst_dt', sa.String(14)),
        sa.Column('openg_dt', sa.String(14)),
        sa.Column('bid_close_dt', sa.String(14)),
        sa.Column('presmpt_prce', sa.BigInteger()),
        sa.Column('main_cnsty_nm', sa.String(200)),
        sa.Column('data', JSONB(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_bid_notices_rgst_dt', 'bid_notices', ['rgst_dt'])
    op.create_index('ix_bid_notices_openg_dt', 'bid_notices', ['openg_dt'])
    op.create_index('ix_bid_notices_bid_close_dt', 'bid_notices', ['bid_close_dt'])

    # bid_basis_amounts - 기초금액 정보
    op.create_table(
        'bid_basis_amounts',
        sa.Column('bid_ntce_no', sa.String(50), primary_key=True),
        sa.Column('bid_ntce_ord', sa.String(10), primary_key=True, server_default='000'),
        sa.Column('bid_type', sa.String(10), primary_key=True),
        sa.Column('data', JSONB(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # bid_prtcpt_psbl_rgns - 참가가능지역 정보
    op.create_table(
        'bid_prtcpt_psbl_rgns',
        sa.Column('bid_ntce_no', sa.String(50), primary_key=True),
        sa.Column('bid_ntce_ord', sa.String(10), primary_key=True),
        sa.Column('lmt_sno', sa.Integer(), primary_key=True),
        sa.Column('prtcpt_psbl_rgn_nm', sa.String(200)),
        sa.Column('rgst_dt', sa.String(30)),
        sa.Column('bsns_div_nm', sa.String(50)),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_bid_prtcpt_psbl_rgns_rgn_nm', 'bid_prtcpt_psbl_rgns', ['prtcpt_psbl_rgn_nm'])

    # user_locations - 사용자 소재지 정보
    op.create_table(
        'user_locations',
        sa.Column('location_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('location_name', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_user_locations_user_id', 'user_locations', ['user_id'])

    # data_sync_log - 동기화 로그
    op.create_table(
        'data_sync_log',
        sa.Column('sync_date', sa.String(8), primary_key=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('total_notices', sa.Integer(), server_default='0'),
        sa.Column('total_regions', sa.Integer(), server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('data_sync_log')
    op.drop_table('user_locations')
    op.drop_table('bid_prtcpt_psbl_rgns')
    op.drop_table('bid_basis_amounts')
    op.drop_table('bid_notices')
