from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bids/estimate-rate", tags=["Estimate Rate"])

MIN_SAMPLE_SIZE = 10
ReserveRateSource = Literal["group_avg", "group_median", "fallback_default"]


class EstimateRateResponse(BaseModel):
    expected_reserve_rate: float = Field(..., description="추정 사정율 (예: 1.025)")
    source: ReserveRateSource
    sample_size: int
    matched_keys: list[str]
    p25: Optional[float] = None
    p75: Optional[float] = None


class DistributionItem(BaseModel):
    bid_ntce_no: str
    bid_ntce_nm: Optional[str] = None
    openg_dt: Optional[str] = None
    bssamt: Optional[int] = None
    plnprc: Optional[int] = None
    reserve_rate: float


class DistributionResponse(BaseModel):
    matched_keys: list[str]
    sample_size: int
    avg_rate: Optional[float] = None
    median_rate: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    items: list[DistributionItem]


def _budget_bucket(amount: Optional[int]) -> Optional[str]:
    if amount is None:
        return None
    if amount <= 100_000_000:
        return "le_1e"
    if amount <= 250_000_000:
        return "1e_2_5e"
    if amount <= 400_000_000:
        return "2_5e_4e"
    if amount <= 1_000_000_000:
        return "4e_10e"
    return "gt_10e"


_LOOKUP_LEVELS: list[tuple[str, ...]] = [
    ("region", "industry", "industry_field", "contract_method", "budget_bucket"),
    ("region", "industry", "industry_field", "budget_bucket"),
    ("region", "industry", "budget_bucket"),
    ("industry", "budget_bucket"),
    ("budget_bucket",),
]

_KEY_TO_RAW_COL = {
    "region": "n.region",
    "industry": "n.industry",
    "industry_field": "n.industry_field",
    "contract_method": "n.contract_method",
    "budget_bucket": "n.budget_bucket",
}


# bid_notices.data 안에는 prtcptPsblRgnNms / permsnIndstrytyListNms /
# indstrytyMfrcFldListNms 가 저장되지 않는다 (응답 합성 시점에만 채워짐).
# raw 통계 계산을 위해 bid_prtcpt_psbl_rgns / bid_license_limits 와 LEFT JOIN 후
# STRING_AGG(DISTINCT ... ORDER BY ...) 로 정렬된 결정적 문자열을 만들어
# 프론트엔드가 보내는 정렬된 query string 과 1:1 매칭한다.
_NOTE_GROUPS_CTE = """
    note_groups AS (
        SELECT
            n.bid_ntce_no,
            n.bid_ntce_ord,
            n.openg_dt,
            n.presmpt_prce,
            n.data->>'bidNtceNm' AS bid_ntce_nm,
            n.data->>'cntrctCnclsMthdNm' AS contract_method,
            budget_bucket(n.presmpt_prce) AS budget_bucket,
            COALESCE((
                SELECT STRING_AGG(DISTINCT r.prtcpt_psbl_rgn_nm, ', ' ORDER BY r.prtcpt_psbl_rgn_nm)
                FROM bid_prtcpt_psbl_rgns r
                WHERE r.bid_ntce_no = n.bid_ntce_no
                  AND r.prtcpt_psbl_rgn_nm IS NOT NULL
                  AND r.prtcpt_psbl_rgn_nm <> ''
            ), '') AS region,
            COALESCE((
                SELECT STRING_AGG(DISTINCT industry_name, ', ' ORDER BY industry_name)
                FROM (
                    SELECT
                        CASE
                            WHEN ll.lcns_lmt_nm IS NOT NULL AND ll.lcns_lmt_nm <> ''
                                -- bid_data_service.py 의 rsplit('/', 1)[0] 와 동일:
                                -- '/' 가 있으면 마지막 '/' 이후를 제거, 없으면 그대로.
                                THEN REGEXP_REPLACE(ll.lcns_lmt_nm, '/[^/]*$', '')
                            WHEN ll.permsn_indstryty_list IS NOT NULL AND ll.permsn_indstryty_list <> ''
                                THEN ll.permsn_indstryty_list
                            ELSE NULL
                        END AS industry_name
                    FROM bid_license_limits ll
                    WHERE ll.bid_ntce_no = n.bid_ntce_no
                ) sub
                WHERE industry_name IS NOT NULL AND industry_name <> ''
            ), '') AS industry,
            COALESCE((
                SELECT STRING_AGG(DISTINCT f, ', ' ORDER BY f)
                FROM bid_license_limits ll,
                     UNNEST(string_to_array(
                         REGEXP_REPLACE(COALESCE(ll.indstryty_mfrc_fld_list, ''), '[\\[\\]]', '', 'g'),
                         '^'
                     )) AS f
                WHERE ll.bid_ntce_no = n.bid_ntce_no
                  AND f <> ''
                  AND f !~ '^[0-9]+$'
            ), '') AS industry_field
        FROM bid_notices n
        WHERE EXISTS (
            SELECT 1 FROM bid_reserve_prices rp
            WHERE rp.bid_ntce_no = n.bid_ntce_no
              AND rp.bid_ntce_ord = n.bid_ntce_ord
              AND rp.fetched_at >= NOW() - INTERVAL '60 days'
        )
    )
"""


def _raw_filter_clause(keys: tuple[str, ...]) -> str:
    """note_groups CTE 의 합성 컬럼들에 grouping key 를 적용하는 WHERE 절."""
    return " AND ".join(
        f"COALESCE({_KEY_TO_RAW_COL[k]}, '') = :{k}" for k in keys
    )


async def _compute_group_stats(
    db: AsyncSession,
    keys: tuple[str, ...],
    values: dict[str, str],
) -> Optional[dict]:
    """raw 사정율 데이터에서 정확한 통계(avg/median/p25/p75)를 계산.

    mv 가중평균은 median/percentile 합산 시 통계적으로 부정확하므로,
    fallback 단계마다 raw 에서 PERCENTILE_CONT 로 직접 계산.
    """
    sql = f"""
        WITH {_NOTE_GROUPS_CTE},
        rates AS (
            SELECT (rp.plnprc::numeric / NULLIF(rp.bssamt, 0)::numeric)::float AS reserve_rate
            FROM bid_reserve_prices rp
            JOIN note_groups n
                 ON n.bid_ntce_no = rp.bid_ntce_no
                AND n.bid_ntce_ord = rp.bid_ntce_ord
            WHERE rp.plnprc IS NOT NULL
              AND rp.bssamt IS NOT NULL
              AND rp.bssamt > 0
              AND rp.fetched_at >= NOW() - INTERVAL '60 days'
              AND {_raw_filter_clause(keys)}
        ),
        filtered AS (
            SELECT reserve_rate FROM rates WHERE reserve_rate BETWEEN 0.5 AND 1.5
        )
        SELECT
            COUNT(*)::int AS total_n,
            AVG(reserve_rate)::float AS avg_rate,
            (PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY reserve_rate))::float AS median_rate,
            (PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY reserve_rate))::float AS p25,
            (PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY reserve_rate))::float AS p75
        FROM filtered
    """
    bind = {k: values[k] for k in keys}
    result = await db.execute(text(sql), bind)
    row = result.mappings().first()
    if not row or not row["total_n"]:
        return None
    return dict(row)


async def _resolve_matched_group(
    db: AsyncSession, values: dict[str, str]
) -> tuple[Optional[tuple[str, ...]], Optional[dict]]:
    """계층적 fallback 으로 첫 번째 충분한 그룹을 찾아 (keys, stats) 반환."""
    for keys in _LOOKUP_LEVELS:
        if any(not values.get(k) for k in keys):
            continue
        stats = await _compute_group_stats(db, keys, values)
        if stats is None:
            continue
        if stats["total_n"] < MIN_SAMPLE_SIZE:
            continue
        return keys, stats
    return None, None


@router.get("", response_model=EstimateRateResponse)
async def get_estimate_rate(
    region: Optional[str] = Query(None, description="참가가능지역명(prtcptPsblRgnNms)"),
    industry: Optional[str] = Query(None, description="허용업종(permsnIndstrytyListNms)"),
    industry_field: Optional[str] = Query(None, description="주력분야(indstrytyMfrcFldListNms)"),
    contract_method: Optional[str] = Query(None, description="계약체결방법명"),
    presmpt_prce: Optional[int] = Query(None, ge=0, description="추정가격 (원)"),
    prefer: Literal["avg", "median"] = Query("avg"),
    db: AsyncSession = Depends(get_db),
) -> EstimateRateResponse:
    """비슷한 공고 그룹의 사정율을 반환 (raw 데이터 기반 PERCENTILE_CONT).

    그룹 정의: [참가지역, 허용업종, 주력분야, 계약방법, 예산범주]

    계층적 fallback (n >= MIN_SAMPLE_SIZE):
      1. (region, industry, industry_field, contract_method, budget_bucket)
      2. (region, industry, industry_field, budget_bucket)
      3. (region, industry, budget_bucket)
      4. (industry, budget_bucket)
      5. (budget_bucket)
      6. fallback_default → 1.0
    """
    values = {
        "region": region or "",
        "industry": industry or "",
        "industry_field": industry_field or "",
        "contract_method": contract_method or "",
        "budget_bucket": _budget_bucket(presmpt_prce) or "",
    }

    keys, stats = await _resolve_matched_group(db, values)
    if keys is None or stats is None:
        return EstimateRateResponse(
            expected_reserve_rate=1.0,
            source="fallback_default",
            sample_size=0,
            matched_keys=[],
        )

    rate = stats["median_rate"] if prefer == "median" else stats["avg_rate"]
    if rate is None:
        return EstimateRateResponse(
            expected_reserve_rate=1.0,
            source="fallback_default",
            sample_size=0,
            matched_keys=[],
        )
    return EstimateRateResponse(
        expected_reserve_rate=float(rate),
        source="group_median" if prefer == "median" else "group_avg",
        sample_size=int(stats["total_n"]),
        matched_keys=list(keys),
        p25=stats["p25"],
        p75=stats["p75"],
    )


@router.get("/distribution", response_model=DistributionResponse)
async def get_estimate_rate_distribution(
    region: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    industry_field: Optional[str] = Query(None),
    contract_method: Optional[str] = Query(None),
    presmpt_prce: Optional[int] = Query(None, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> DistributionResponse:
    """동일 그룹 키의 raw 사정율 분포를 반환합니다.

    통계(avg/median/p25/p75/sample_size)는 LIMIT 무관하게 전체 그룹에서 산출.
    items 만 최근순 LIMIT 적용 (UI 용 샘플링).
    """
    values = {
        "region": region or "",
        "industry": industry or "",
        "industry_field": industry_field or "",
        "contract_method": contract_method or "",
        "budget_bucket": _budget_bucket(presmpt_prce) or "",
    }

    keys, stats = await _resolve_matched_group(db, values)
    if keys is None or stats is None:
        return DistributionResponse(
            matched_keys=[],
            sample_size=0,
            items=[],
        )

    bind: dict[str, object] = {"limit": limit}
    bind.update({k: values[k] for k in keys})
    items_sql = f"""
        WITH {_NOTE_GROUPS_CTE}
        SELECT
            rp.bid_ntce_no,
            rp.bid_ntce_ord,
            n.bid_ntce_nm,
            n.openg_dt,
            rp.bssamt,
            rp.plnprc,
            (rp.plnprc::numeric / NULLIF(rp.bssamt, 0)::numeric)::float AS reserve_rate
        FROM bid_reserve_prices rp
        JOIN note_groups n
             ON n.bid_ntce_no = rp.bid_ntce_no
            AND n.bid_ntce_ord = rp.bid_ntce_ord
        WHERE rp.plnprc IS NOT NULL
          AND rp.bssamt IS NOT NULL
          AND rp.bssamt > 0
          AND rp.fetched_at >= NOW() - INTERVAL '60 days'
          AND (rp.plnprc::numeric / NULLIF(rp.bssamt, 0)::numeric) BETWEEN 0.5 AND 1.5
          AND {_raw_filter_clause(keys)}
        ORDER BY n.openg_dt DESC NULLS LAST
        LIMIT :limit
    """
    result = await db.execute(text(items_sql), bind)
    rows: list[DistributionItem] = []
    for r in result.mappings():
        rows.append(
            DistributionItem(
                bid_ntce_no=r["bid_ntce_no"],
                bid_ntce_nm=r["bid_ntce_nm"],
                openg_dt=r["openg_dt"],
                bssamt=r["bssamt"],
                plnprc=r["plnprc"],
                reserve_rate=float(r["reserve_rate"]),
            )
        )

    return DistributionResponse(
        matched_keys=list(keys),
        sample_size=int(stats["total_n"]),
        avg_rate=stats["avg_rate"],
        median_rate=stats["median_rate"],
        p25=stats["p25"],
        p75=stats["p75"],
        items=rows,
    )
