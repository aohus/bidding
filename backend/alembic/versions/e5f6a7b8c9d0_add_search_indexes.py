"""add search performance indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-10 22:30:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 추정가격 범위 필터 인덱스
    op.create_index(
        'ix_bid_notices_presmpt_prce',
        'bid_notices',
        ['presmpt_prce'],
    )

    # 지역 테이블 bid_ntce_no + bid_ntce_ord (EXISTS 서브쿼리 최적화)
    op.create_index(
        'ix_bid_prtcpt_psbl_rgns_bid_ntce',
        'bid_prtcpt_psbl_rgns',
        ['bid_ntce_no', 'bid_ntce_ord'],
    )

    # 공사현장지역명 JSONB expression index (partial)
    op.execute(
        "CREATE INDEX ix_bid_notices_cnstrtsite ON bid_notices "
        "((data->>'cnstrtsiteRgnNm')) "
        "WHERE data->>'cnstrtsiteRgnNm' IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bid_notices_cnstrtsite")
    op.drop_index('ix_bid_prtcpt_psbl_rgns_bid_ntce', table_name='bid_prtcpt_psbl_rgns')
    op.drop_index('ix_bid_notices_presmpt_prce', table_name='bid_notices')
