"""외부기관(비-나라장터) 공고 수집 테이블 추가

LH / 수자원 / 지역난방 / 마사회 / 가스공사 / 전력개발포털 공고를 수집한다.
기존 bid_notices 와 분리한 이유는 app/models/external_bid.py 주석 참조.

source 를 PK 선두에 두어 기관 간 공고번호 체계 충돌을 차단한다.
순수 신규 테이블 3개 추가로, 기존 데이터에 영향이 없다.

Revision ID: l3b4c5d6e7f8
Revises: k2a3b4c5d6e7
Create Date: 2026-10-12 17:05:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "l3b4c5d6e7f8"
down_revision = "k2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_bid_notices",
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("notice_no", sa.String(length=60), nullable=False),
        sa.Column(
            "notice_ord", sa.String(length=10), nullable=False,
            server_default="000",
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("institution", sa.String(length=300), nullable=True),
        sa.Column("work_div", sa.String(length=50), nullable=True),
        sa.Column("cntrct_mthd", sa.String(length=100), nullable=True),
        sa.Column("rgst_dt", sa.String(length=14), nullable=True),
        sa.Column("bid_close_dt", sa.String(length=14), nullable=True),
        sa.Column("openg_dt", sa.String(length=14), nullable=True),
        sa.Column("presmpt_prce", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("source", "notice_no", "notice_ord"),
    )
    op.create_index(
        "ix_external_bid_notices_rgst_dt", "external_bid_notices", ["rgst_dt"]
    )
    op.create_index(
        "ix_external_bid_notices_openg_dt", "external_bid_notices", ["openg_dt"]
    )
    op.create_index(
        "ix_external_bid_notices_bid_close_dt",
        "external_bid_notices",
        ["bid_close_dt"],
    )
    op.create_index(
        "ix_external_bid_notices_source_rgst_dt",
        "external_bid_notices",
        ["source", "rgst_dt"],
    )

    op.create_table(
        "external_bid_results",
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("notice_no", sa.String(length=60), nullable=False),
        sa.Column(
            "notice_ord", sa.String(length=10), nullable=False,
            server_default="000",
        ),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("bidder_nm", sa.String(length=300), nullable=True),
        sa.Column("bidder_amt", sa.BigInteger(), nullable=True),
        sa.Column("status_nm", sa.String(length=100), nullable=True),
        sa.Column("openg_dt", sa.String(length=14), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("source", "notice_no", "notice_ord", "seq"),
    )
    op.create_index(
        "ix_external_bid_results_openg_dt", "external_bid_results", ["openg_dt"]
    )

    op.create_table(
        "external_sync_log",
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.String(length=12), nullable=False),
        sa.Column("window_end", sa.String(length=12), nullable=False),
        sa.Column("total_notices", sa.Integer(), server_default="0"),
        sa.Column("total_results", sa.Integer(), server_default="0"),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("source", "window_start", "window_end"),
    )


def downgrade() -> None:
    op.drop_table("external_sync_log")
    op.drop_index(
        "ix_external_bid_results_openg_dt", table_name="external_bid_results"
    )
    op.drop_table("external_bid_results")
    op.drop_index(
        "ix_external_bid_notices_source_rgst_dt",
        table_name="external_bid_notices",
    )
    op.drop_index(
        "ix_external_bid_notices_bid_close_dt",
        table_name="external_bid_notices",
    )
    op.drop_index(
        "ix_external_bid_notices_openg_dt", table_name="external_bid_notices"
    )
    op.drop_index(
        "ix_external_bid_notices_rgst_dt", table_name="external_bid_notices"
    )
    op.drop_table("external_bid_notices")
