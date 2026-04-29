"""drop unused mv_estimate_rate_stats

Revision ID: i0e1f2a3b4c5
Revises: h9d0e1f2a3b4
Create Date: 2026-04-29

mv_estimate_rate_stats 는 도입 시점부터 SELECT 사용처가 없었고,
estimate_rate API 는 raw bid_reserve_prices+bid_notices 직접 쿼리로 동작.
주기적 REFRESH 비용만 발생하므로 정리.

budget_bucket(BIGINT) PG 함수는 estimate_rate API SQL 에서 계속 사용되므로 유지.
"""
from alembic import op

revision = "i0e1f2a3b4c5"
down_revision = "h9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_estimate_rate_stats CASCADE")


def downgrade() -> None:
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
