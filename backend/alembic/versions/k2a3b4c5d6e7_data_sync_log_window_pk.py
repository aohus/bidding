"""data_sync_log PK 를 (sync_timestamp, window_end) 로 확장

시간별 00시 윈도우와 일별 백필 윈도우가 같은 sync_timestamp(YYYYMMDD0000)를
쓰기 때문에 서로를 덮어썼다. mark_window_synced 가 window_end 를 갱신하므로
00시 시간별 동기화가 한 번이라도 돌면 그 날 행의 window_end 가 0059 로 바뀌고,
_backfill_past_days / sync_recent_data 는 window_end 를 보지 않고 skip 하기
때문에 해당 일자가 자동/수동 어느 쪽으로도 다시 동기화되지 않았다.

window_end 를 PK 에 포함시켜 두 윈도우가 공존하도록 한다.
  - 시간별: ('202608040000', '202608040059')
  - 일별  : ('202608040000', '202608042359')

기존 PK 가 sync_timestamp 단일 컬럼이므로 중복 행이 존재할 수 없어
업그레이드는 무손실이다.

Revision ID: k2a3b4c5d6e7
Revises: j1f2a3b4c5d6
Create Date: 2026-08-05 14:10:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "k2a3b4c5d6e7"
down_revision = "j1f2a3b4c5d6"
branch_labels = None
depends_on = None

# 기존 PK 제약 이름을 가정하지 않는다. f6a7b8c9d0e1 이 rename_table 로 테이블을
# 만들었는데 RENAME 은 제약/인덱스 이름을 바꾸지 않으므로, 새 테이블의 PK 가
# 'data_sync_log_pkey1' 처럼 자동 중복회피 이름을 갖고 있을 수 있다.
_DROP_EXISTING_PK = """
DO $$
DECLARE
    pk_name text;
BEGIN
    SELECT conname INTO pk_name
    FROM pg_constraint
    WHERE conrelid = 'data_sync_log'::regclass
      AND contype = 'p';

    IF pk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE data_sync_log DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute("ALTER TABLE data_sync_log ALTER COLUMN window_end SET NOT NULL")
    op.execute(_DROP_EXISTING_PK)
    # 이름은 PostgreSQL 이 정하도록 둔다 (기존 인덱스명 충돌 회피).
    op.execute(
        "ALTER TABLE data_sync_log "
        "ADD PRIMARY KEY (sync_timestamp, window_end)"
    )


def downgrade() -> None:
    # 단일 컬럼 PK 로 되돌리려면 sync_timestamp 당 1행만 남겨야 한다.
    # 가장 최근에 동기화된 행(일별 윈도우일 가능성이 높음)을 유지한다.
    op.execute(
        """
        DELETE FROM data_sync_log a
        USING data_sync_log b
        WHERE a.sync_timestamp = b.sync_timestamp
          AND (a.synced_at, a.window_end) < (b.synced_at, b.window_end)
        """
    )
    op.execute(_DROP_EXISTING_PK)
    op.execute("ALTER TABLE data_sync_log ADD PRIMARY KEY (sync_timestamp)")
