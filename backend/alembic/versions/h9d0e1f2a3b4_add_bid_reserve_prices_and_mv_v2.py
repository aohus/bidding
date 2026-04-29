"""add bid_reserve_prices table and recreate mv_estimate_rate_stats v2 (plnprc-based)

Revision ID: h9d0e1f2a3b4
Revises: g8c9d0e1f2a3
Create Date: 2026-04-29

정확한 사정율(`plnprc / bssamt`) 사용을 위해:
  1) `bid_reserve_prices` 테이블 신규 추가
  2) 기존 mv_estimate_rate_stats (1등 입찰가 역산 기반) 삭제 후
     plnprc 기반 v2 로 재생성
"""
from alembic import op

revision = "h9d0e1f2a3b4"
down_revision = "g8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bid_reserve_prices (
            bid_ntce_no VARCHAR(50) NOT NULL,
            bid_ntce_ord VARCHAR(10) NOT NULL DEFAULT '000',
            bid_type VARCHAR(10) NOT NULL,
            bssamt BIGINT,
            plnprc BIGINT,
            bsis_plnprc BIGINT,
            rl_openg_dt VARCHAR(20),
            data JSONB,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (bid_ntce_no, bid_ntce_ord, bid_type)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_bid_reserve_prices_fetched_at
        ON bid_reserve_prices (fetched_at)
        """
    )

    # 기존 v1 mv 삭제 후 plnprc 기반 v2 재생성
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_estimate_rate_stats")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_estimate_rate_stats AS
        WITH rates AS (
            SELECT
                n.data->>'cnstrtsiteRgnNm' AS region,
                n.data->>'permsnIndstrytyListNms' AS industry,
                n.data->>'cntrctCnclsMthdNm' AS contract_method,
                budget_bucket(n.presmpt_prce) AS budget_bucket,
                rp.plnprc::numeric / NULLIF(rp.bssamt, 0)::numeric AS reserve_rate
            FROM bid_reserve_prices rp
            JOIN bid_notices n
                 ON n.bid_ntce_no = rp.bid_ntce_no
                AND n.bid_ntce_ord = rp.bid_ntce_ord
            WHERE rp.plnprc IS NOT NULL
              AND rp.bssamt IS NOT NULL
              AND rp.bssamt > 0
              AND rp.fetched_at >= NOW() - INTERVAL '60 days'
        )
        SELECT
            COALESCE(region, '') AS region,
            COALESCE(industry, '') AS industry,
            COALESCE(contract_method, '') AS contract_method,
            COALESCE(budget_bucket, '') AS budget_bucket,
            COUNT(*)::integer AS sample_size,
            AVG(reserve_rate)::numeric(10, 6) AS avg_rate,
            (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY reserve_rate))::numeric(10, 6) AS median_rate,
            (PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY reserve_rate))::numeric(10, 6) AS p25_rate,
            (PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY reserve_rate))::numeric(10, 6) AS p75_rate,
            NOW() AS refreshed_at
        FROM rates
        WHERE reserve_rate BETWEEN 0.5 AND 1.5
        GROUP BY region, industry, contract_method, budget_bucket
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_estimate_rate_stats_keys
        ON mv_estimate_rate_stats (region, industry, contract_method, budget_bucket)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mv_estimate_rate_stats_region_bucket
        ON mv_estimate_rate_stats (region, budget_bucket)
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_estimate_rate_stats")
    op.execute("DROP TABLE IF EXISTS bid_reserve_prices")
