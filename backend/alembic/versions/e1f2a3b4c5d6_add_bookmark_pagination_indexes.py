"""add bookmark pagination indexes

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-04-23

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_user_bookmarks_user_id",
            table_name="user_bookmarks",
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_user_bookmarks_user_status_created",
            "user_bookmarks",
            ["user_id", "status", "created_at"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_user_bookmarks_notice_ord",
            "user_bookmarks",
            ["bid_notice_no", "bid_notice_ord"],
            postgresql_concurrently=True,
        )
    op.create_table(
        "bookmark_dashboard_items",
        sa.Column("bookmark_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bid_notice_no", sa.String(50), nullable=False),
        sa.Column("bid_notice_ord", sa.String(10), nullable=True),
        sa.Column("bid_notice_name", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("bid_price", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bid_close_dt", sa.String(14), nullable=True),
        sa.Column("openg_dt", sa.String(14), nullable=True),
        sa.Column(
            "openg_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("actual_bid_price", sa.String(50), nullable=True),
        sa.Column("bid_rate", sa.String(50), nullable=True),
        sa.Column("rank_value", sa.Integer(), nullable=True),
        sa.Column("total_bidders", sa.Integer(), nullable=True),
        sa.Column("winning_bid_price", sa.String(50), nullable=True),
        sa.Column("winning_bid_rate", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(
            ["bookmark_id"],
            ["user_bookmarks.bookmark_id"],
            ondelete="CASCADE",
        ),
    )
    op.execute(
        """
        INSERT INTO bookmark_dashboard_items (
            bookmark_id, user_id, bid_notice_no, bid_notice_ord,
            bid_notice_name, status, bid_price, notes, created_at, updated_at,
            bid_close_dt, openg_dt, openg_completed,
            actual_bid_price, bid_rate, rank_value, total_bidders,
            winning_bid_price, winning_bid_rate
        )
        SELECT
            b.bookmark_id,
            b.user_id,
            b.bid_notice_no,
            COALESCE(NULLIF(b.bid_notice_ord, ''), '000'),
            b.bid_notice_name,
            b.status,
            b.bid_price,
            b.notes,
            COALESCE(b.created_at, NOW()),
            b.updated_at,
            n.bid_close_dt,
            n.openg_dt,
            COALESCE(r.data IS NOT NULL AND jsonb_array_length(r.data) > 0, false),
            COALESCE(mine.value->>'bidprcAmt', CASE WHEN b.bid_price IS NOT NULL THEN b.bid_price::text ELSE NULL END),
            mine.value->>'bidprcrt',
            CASE
                WHEN NULLIF(BTRIM(mine.value->>'opengRank'), '') ~ '^-?[0-9]+$'
                    THEN NULLIF(BTRIM(mine.value->>'opengRank'), '')::integer
                WHEN mine.value IS NOT NULL THEN -(
                    SELECT COUNT(*) + 1
                    FROM jsonb_array_elements(COALESCE(r.data, '[]'::jsonb)) AS u(value)
                    WHERE NULLIF(BTRIM(COALESCE(u.value->>'opengRank', '')), '') IS NULL
                      AND CASE
                            WHEN NULLIF(u.value->>'bidprcrt', '') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                                THEN NULLIF(u.value->>'bidprcrt', '')::numeric
                            ELSE NULL
                          END >
                          CASE
                            WHEN NULLIF(mine.value->>'bidprcrt', '') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                                THEN NULLIF(mine.value->>'bidprcrt', '')::numeric
                            ELSE NULL
                          END
                )::integer
                ELSE NULL
            END,
            CASE WHEN r.data IS NOT NULL THEN jsonb_array_length(r.data) ELSE NULL END,
            winner.value->>'bidprcAmt',
            winner.value->>'bidprcrt'
        FROM user_bookmarks b
        LEFT JOIN bid_notices n
          ON n.bid_ntce_no = b.bid_notice_no
         AND n.bid_ntce_ord = COALESCE(NULLIF(b.bid_notice_ord, ''), '000')
        LEFT JOIN bid_opening_results r
          ON r.bid_ntce_no = b.bid_notice_no
         AND r.bid_ntce_ord = COALESCE(NULLIF(b.bid_notice_ord, ''), '000')
        LEFT JOIN LATERAL (
            SELECT e.value
            FROM jsonb_array_elements(COALESCE(r.data, '[]'::jsonb)) WITH ORDINALITY AS e(value, ord)
            WHERE e.value->>'opengRank' = '1'
            ORDER BY e.ord
            LIMIT 1
        ) winner ON true
        LEFT JOIN users u ON u.user_id = b.user_id
        LEFT JOIN LATERAL (
            SELECT e.value
            FROM jsonb_array_elements(COALESCE(r.data, '[]'::jsonb)) WITH ORDINALITY AS e(value, ord)
            WHERE NULLIF(REPLACE(COALESCE(u.business_number, ''), '-', ''), '') IS NOT NULL
              AND REPLACE(COALESCE(e.value->>'prcbdrBizno', ''), '-', '') = REPLACE(COALESCE(u.business_number, ''), '-', '')
            ORDER BY e.ord
            LIMIT 1
        ) mine ON true
        """
    )
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_bookmark_dashboard_user_status_openg",
            "bookmark_dashboard_items",
            ["user_id", "status", "openg_dt"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_bookmark_dashboard_user_status_close",
            "bookmark_dashboard_items",
            ["user_id", "status", "bid_close_dt"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_bookmark_dashboard_user_status_created",
            "bookmark_dashboard_items",
            ["user_id", "status", "created_at"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_bookmark_dashboard_user_status_rank",
            "bookmark_dashboard_items",
            ["user_id", "status", "rank_value"],
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_bookmark_dashboard_notice_ord",
            "bookmark_dashboard_items",
            ["bid_notice_no", "bid_notice_ord"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_bookmark_dashboard_notice_ord",
            table_name="bookmark_dashboard_items",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_bookmark_dashboard_user_status_rank",
            table_name="bookmark_dashboard_items",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_bookmark_dashboard_user_status_created",
            table_name="bookmark_dashboard_items",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_bookmark_dashboard_user_status_close",
            table_name="bookmark_dashboard_items",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_bookmark_dashboard_user_status_openg",
            table_name="bookmark_dashboard_items",
            postgresql_concurrently=True,
        )
    op.drop_table("bookmark_dashboard_items")
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_user_bookmarks_notice_ord",
            table_name="user_bookmarks",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_user_bookmarks_user_status_created",
            table_name="user_bookmarks",
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_user_bookmarks_user_id",
            "user_bookmarks",
            ["user_id"],
            postgresql_concurrently=True,
        )
