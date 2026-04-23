"""add bookmark_dashboard_items read model

Revision ID: f7b8c9d0e1f2
Revises: e1f2a3b4c5d6
Create Date: 2026-04-23

Creates the bookmark_dashboard_items read-model table idempotently.
Safe to run on environments where an earlier (rewritten-in-place) version
of revision e1f2a3b4c5d6 already created the table.
"""
from alembic import op

revision = "f7b8c9d0e1f2"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bookmark_dashboard_items (
            bookmark_id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            bid_notice_no VARCHAR(50) NOT NULL,
            bid_notice_ord VARCHAR(10),
            bid_notice_name VARCHAR(500) NOT NULL,
            status VARCHAR(20) NOT NULL,
            bid_price BIGINT,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ,
            bid_close_dt VARCHAR(14),
            openg_dt VARCHAR(14),
            openg_completed BOOLEAN NOT NULL DEFAULT false,
            actual_bid_price VARCHAR(50),
            bid_rate VARCHAR(50),
            rank_value INTEGER,
            total_bidders INTEGER,
            winning_bid_price VARCHAR(50),
            winning_bid_rate VARCHAR(50),
            CONSTRAINT fk_bookmark_dashboard_items_bookmark_id
                FOREIGN KEY (bookmark_id)
                REFERENCES user_bookmarks(bookmark_id)
                ON DELETE CASCADE
        )
        """
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
        ON CONFLICT (bookmark_id) DO NOTHING
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bookmark_dashboard_user_status_openg "
        "ON bookmark_dashboard_items (user_id, status, openg_dt)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bookmark_dashboard_user_status_close "
        "ON bookmark_dashboard_items (user_id, status, bid_close_dt)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bookmark_dashboard_user_status_created "
        "ON bookmark_dashboard_items (user_id, status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bookmark_dashboard_user_status_rank "
        "ON bookmark_dashboard_items (user_id, status, rank_value)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bookmark_dashboard_notice_ord "
        "ON bookmark_dashboard_items (bid_notice_no, bid_notice_ord)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bookmark_dashboard_notice_ord")
    op.execute("DROP INDEX IF EXISTS ix_bookmark_dashboard_user_status_rank")
    op.execute("DROP INDEX IF EXISTS ix_bookmark_dashboard_user_status_created")
    op.execute("DROP INDEX IF EXISTS ix_bookmark_dashboard_user_status_close")
    op.execute("DROP INDEX IF EXISTS ix_bookmark_dashboard_user_status_openg")
    op.execute("DROP TABLE IF EXISTS bookmark_dashboard_items")
