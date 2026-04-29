"""cleanup unused reserve_price sentinel rows

Revision ID: j1f2a3b4c5d6
Revises: i0e1f2a3b4c5
Create Date: 2026-04-29

이전 sentinel 패치가 잠시 적용되어 bid_type='unknown' 인 negative cache row 가
누적되어 있을 수 있음. 그러나 root cause 가 inqryDiv 누락 (클라 측 버그) 으로
판명되어 sentinel 차단은 잘못된 fix. 모두 삭제하여 다음 sync cycle 에서
정상 inqryDiv=2 호출로 plnprc 가 채워지도록 한다.

idempotent: sentinel row 가 없으면 0 rows 삭제.
"""
from alembic import op

revision = "j1f2a3b4c5d6"
down_revision = "i0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM bid_reserve_prices WHERE bid_type = 'unknown'"
    )


def downgrade() -> None:
    # sentinel 데이터는 의미가 없어 복원하지 않음.
    pass
