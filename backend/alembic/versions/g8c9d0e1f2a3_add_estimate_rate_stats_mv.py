"""add estimate_rate_stats materialized view

Revision ID: g8c9d0e1f2a3
Revises: f7b8c9d0e1f2
Create Date: 2026-04-29

비슷한 공고 그룹(참가지역 / 허용업종 / 계약방법 / 예산범주)별 사정율 통계.
사정율 ≈ 1등 입찰가율 / 낙찰하한율 (A값 무시 단순 추정).

Materialized view + helper budget_bucket() function.
주 1회 (일요일) `REFRESH MATERIALIZED VIEW CONCURRENTLY` 호출.
"""
from alembic import op

revision = "g8c9d0e1f2a3"
down_revision = "f7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 예산 범주 분류 함수 (presmpt_prce 기준)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION budget_bucket(amount BIGINT)
        RETURNS TEXT AS $$
        BEGIN
            IF amount IS NULL THEN
                RETURN NULL;
            ELSIF amount <= 100000000 THEN
                RETURN 'le_1e';
            ELSIF amount <= 250000000 THEN
                RETURN '1e_2_5e';
            ELSIF amount <= 400000000 THEN
                RETURN '2_5e_4e';
            ELSIF amount <= 1000000000 THEN
                RETURN '4e_10e';
            ELSE
                RETURN 'gt_10e';
            END IF;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )

    # 사정율 통계 materialized view
    # 그룹 키: (region, industry, contract_method, budget_bucket)
    # 사정율 추정: 1등 입찰가율(bidprcrt %) / 낙찰하한율(sucsfbidLwltRate %) → 비율
    # 최근 30일 윈도우 (rolling)
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_estimate_rate_stats AS
        WITH winners AS (
            SELECT
                n.bid_ntce_no,
                n.bid_ntce_ord,
                n.presmpt_prce,
                n.data->>'cnstrtsiteRgnNm' AS region,
                n.data->>'permsnIndstrytyListNms' AS industry,
                n.data->>'cntrctCnclsMthdNm' AS contract_method,
                NULLIF(n.data->>'sucsfbidLwltRate', '')::numeric AS lower_limit_rate,
                NULLIF(w.value->>'bidprcrt', '')::numeric AS winner_rate
            FROM bid_notices n
            JOIN bid_opening_results r
                 ON r.bid_ntce_no = n.bid_ntce_no
                AND r.bid_ntce_ord = n.bid_ntce_ord
            CROSS JOIN LATERAL jsonb_array_elements(COALESCE(r.data, '[]'::jsonb)) AS w(value)
            WHERE w.value->>'opengRank' = '1'
              AND r.fetched_at >= NOW() - INTERVAL '30 days'
        ),
        rates AS (
            SELECT
                region,
                industry,
                contract_method,
                budget_bucket(presmpt_prce) AS budget_bucket,
                CASE
                    WHEN lower_limit_rate IS NOT NULL AND lower_limit_rate > 0
                        THEN winner_rate / lower_limit_rate
                    ELSE NULL
                END AS reserve_rate
            FROM winners
            WHERE winner_rate IS NOT NULL
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
        WHERE reserve_rate IS NOT NULL
          AND reserve_rate BETWEEN 0.5 AND 1.5
        GROUP BY region, industry, contract_method, budget_bucket;
        """
    )

    # CONCURRENTLY REFRESH 위해 unique index 필수
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_estimate_rate_stats_keys
        ON mv_estimate_rate_stats (region, industry, contract_method, budget_bucket);
        """
    )

    # 부분 lookup용 인덱스
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mv_estimate_rate_stats_region_bucket
        ON mv_estimate_rate_stats (region, budget_bucket);
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_estimate_rate_stats")
    op.execute("DROP FUNCTION IF EXISTS budget_bucket(BIGINT)")
