"""가산지역/공동도급의무지역/부공종 데이터를 과거 N일치 백필합니다.

배경:
    API 02 전환으로 추가된 3개 데이터셋(bid_incntv_rgns,
    bid_jntcontrct_duty_rgns, bid_subsi_cnsttys)은 시간별 동기화부터
    수집된다. 마이그레이션 이전 공고는 이 스크립트로 채운다.

    - 일별 윈도우(YYYYMMDD0000 ~ YYYYMMDD2359)로 3개 데이터셋만 수집/저장
    - bid_notices 는 건드리지 않는다 (upsert 라 재실행 안전)
    - 3종이 모두 성공한 날은 data_sync_log.sub_datasets_synced=true 로 표시한다
      (해당 일별 윈도우 행이 있을 때만; 없으면 no-op)
    - 이 스크립트는 선택적 빠른 경로다. 스케줄러가 sub_datasets_synced=false 인
      일별 윈도우를 사이클당 5개씩 자동 재수집하므로 기다려도 채워진다.
    - 일부 데이터셋이 실패해도 다음 날짜로 계속 진행하고, 마지막에 실패가
      있으면 종료 코드 1 로 끝난다.

사용법:
    python scripts/backfill_bid_sub_datasets.py            # 최근 30일
    python scripts/backfill_bid_sub_datasets.py 7          # 최근 7일
    python scripts/backfill_bid_sub_datasets.py 7 --dry-run  # 저장 없이 건수만
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.narajangter import NaraJangterService, narajangter_service  # noqa: E402
from app.services.service_key_rotator import redact_service_key  # noqa: E402

DEFAULT_DAYS = 30
MAX_DAYS = 365
PAGE_DELAY_SECONDS = 0.5


def past_days(days: int, today: datetime | None = None) -> list[str]:
    """오늘 포함 최근 N일(YYYYMMDD), 과거 -> 현재 순."""
    if days < 1 or days > MAX_DAYS:
        raise SystemExit(f"days 는 1~{MAX_DAYS} 사이여야 합니다: {days}")
    base = (today or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    return [(base - timedelta(days=i)).strftime("%Y%m%d") for i in range(days - 1, -1, -1)]


def build_datasets(save_target=None) -> list[tuple[str, object, object]]:
    """(라벨, fetch(bgn,end,page), save(db, rows)) 목록."""
    if save_target is None:
        from app.services.bid_data_service import bid_data_service as save_target

    return [
        ("가산지역", narajangter_service.get_incntv_rgn_by_date,
         save_target.save_incntv_rgns),
        ("공동도급의무지역", narajangter_service.get_jntcontrct_duty_rgn_by_date,
         save_target.save_jntcontrct_duty_rgns),
        ("부공종", narajangter_service.get_subsi_cnstty_by_date,
         save_target.save_subsi_cnsttys),
    ]


async def backfill_dataset(label, fetch, save, db, day: str, dry_run: bool) -> tuple[int, bool]:
    """한 데이터셋의 하루치를 페이지 단위로 수집. (건수, 성공 여부)"""
    bgn, end = f"{day}0000", f"{day}2359"
    total, page = 0, 1
    while True:
        try:
            rows = await fetch(bgn, end, page)
        except Exception as exc:  # noqa: BLE001
            keys = list(getattr(narajangter_service, "_service_keys", []) or [])
            msg = redact_service_key(f"{type(exc).__name__}: {exc}", keys)
            print(f"  {label}: 실패 (page {page}): {msg}")
            return total, False
        if not rows:
            break
        if not dry_run:
            await save(db, rows)
        total += len(rows)
        if len(rows) < NaraJangterService.MAX_PAGE_SIZE:
            break
        page += 1
        await asyncio.sleep(PAGE_DELAY_SECONDS)
    return total, True


async def mark_day_done(db, day: str, counts: list[int]) -> None:
    """3종 모두 성공한 날의 일별 윈도우에 sub_datasets_synced 를 표시한다."""
    from app.services.bid_data_service import bid_data_service

    await bid_data_service.mark_sub_datasets_synced(
        db, f"{day}0000", f"{day}2359", *counts
    )


async def run(days: list[str], dry_run: bool, db=None, datasets=None) -> bool:
    """전체 실행. 모든 데이터셋/날짜가 성공하면 True."""
    datasets = datasets or build_datasets()
    all_ok = True
    for day in days:
        print(f"[{day}]")
        day_ok, counts = True, []
        for label, fetch, save in datasets:
            total, ok = await backfill_dataset(label, fetch, save, db, day, dry_run)
            day_ok = day_ok and ok
            counts.append(total)
            print(f"  {label}: {total}건{'' if ok else ' (일부 실패)'}")
        all_ok = all_ok and day_ok
        if day_ok and not dry_run and db is not None and len(counts) == 3:
            await mark_day_done(db, day, counts)
        await asyncio.sleep(PAGE_DELAY_SECONDS)
    return all_ok


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("days", nargs="?", type=int, default=DEFAULT_DAYS,
                    help=f"최근 N일 (기본 {DEFAULT_DAYS})")
    ap.add_argument("--dry-run", action="store_true", help="DB 저장 없이 건수만 확인")
    args = ap.parse_args()

    days = past_days(args.days)
    print(f"=== 부속 데이터셋 백필{' (dry-run)' if args.dry_run else ''}: "
          f"{days[0]} ~ {days[-1]} ({len(days)}일) ===\n")

    if args.dry_run:
        ok = await run(days, True)
    else:
        from app.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            ok = await run(days, False, db)
    print("\n완료" if ok else "\n일부 실패 - 로그 확인 후 재실행하세요 (upsert 라 안전)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
