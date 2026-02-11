"""migrate data_sync_log to timestamp-based windows

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-11 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 기존 테이블 이름 변경 (데이터 보존, 원자적)
    op.rename_table("data_sync_log", "data_sync_log_old")

    # 2. 새 스키마로 테이블 생성
    op.create_table(
        "data_sync_log",
        sa.Column("sync_timestamp", sa.String(12), primary_key=True),
        sa.Column("window_end", sa.String(12), nullable=False),
        sa.Column("total_notices", sa.Integer(), default=0),
        sa.Column("total_regions", sa.Integer(), default=0),
        sa.Column("total_license_limits", sa.Integer(), default=0),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 3. 기존 날짜별 데이터를 일별 윈도우로 변환
    op.execute(
        """
        INSERT INTO data_sync_log
            (sync_timestamp, window_end, total_notices, total_regions,
             total_license_limits, synced_at)
        SELECT
            sync_date || '0000',
            sync_date || '2359',
            COALESCE(total_notices, 0),
            COALESCE(total_regions, 0),
            COALESCE(total_license_limits, 0),
            COALESCE(synced_at, NOW())
        FROM data_sync_log_old
        """
    )

    # 4. 이전 테이블 삭제
    op.drop_table("data_sync_log_old")


def downgrade() -> None:
    # 1. 현재 테이블 이름 변경
    op.rename_table("data_sync_log", "data_sync_log_new")

    # 2. 기존 스키마 복원
    op.create_table(
        "data_sync_log",
        sa.Column("sync_date", sa.String(8), primary_key=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("total_notices", sa.Integer(), default=0),
        sa.Column("total_regions", sa.Integer(), default=0),
        sa.Column("total_license_limits", sa.Integer(), default=0),
    )

    # 3. 날짜별로 집계하여 복원 (시간별+일별 윈도우 모두 포함)
    op.execute(
        """
        INSERT INTO data_sync_log
            (sync_date, total_notices, total_regions,
             total_license_limits, synced_at)
        SELECT
            LEFT(sync_timestamp, 8),
            SUM(total_notices),
            SUM(total_regions),
            SUM(total_license_limits),
            MAX(synced_at)
        FROM data_sync_log_new
        GROUP BY LEFT(sync_timestamp, 8)
        ON CONFLICT (sync_date) DO NOTHING
        """
    )

    op.drop_table("data_sync_log_new")
