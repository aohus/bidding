"""지정한 날짜를 강제로 재동기화합니다 (data_sync_log skip 로직 우회).

배경:
    scheduler.sync_window() 는 data_sync_log 를 조회하지 않고
    _sync_window_internal 을 바로 호출하므로, 이미 완료로 기록된 날짜도
    무조건 다시 수집한다. 개별 공고 누락이 확인됐을 때의 복구 경로다.

    완료 시 mark_window_synced 가 (YYYYMMDD0000, YYYYMMDD2359) 행을 남기므로
    이후 일별 백필이 그 날을 정상적으로 완료 처리한다.

    같은 일을 운영 API 로 하려면: POST /bids/sync?days=N&force=true

사용법:
    # 하루만
    python scripts/resync_window.py 20260804

    # 범위
    python scripts/resync_window.py 20260801 20260805

    # DB 없이 API 응답만 확인 (수집될 건수 미리보기)
    python scripts/resync_window.py 20260804 --dry-run

    # 특정 공고가 실제로 잡히는지까지 확인
    python scripts/resync_window.py 20260804 --dry-run --notice R26BK01665863
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.bid import BidSearchParams  # noqa: E402
from app.services.narajangter import (  # noqa: E402
    NaraJangterService,
    narajangter_service,
)


def daterange(start: str, end: str) -> list[str]:
    s = datetime.strptime(start, "%Y%m%d")
    e = datetime.strptime(end, "%Y%m%d")
    if e < s:
        raise SystemExit(f"종료일({end})이 시작일({start})보다 빠릅니다")
    out = []
    while s <= e:
        out.append(s.strftime("%Y%m%d"))
        s += timedelta(days=1)
    return out


async def preview_day(day: str, notice: str | None) -> None:
    """API 만 호출해서 해당 일자에 수집될 건수를 보여줍니다 (DB 미사용)."""
    bgn, end = f"{day}0000", f"{day}2359"
    found_in = []

    for work_type in ("contract", "service"):
        total = 0
        page = 1
        while True:
            params = BidSearchParams(
                inqryDiv="1",
                inqryBgnDt=bgn,
                inqryEndDt=end,
                numOfRows=100,
                pageNo=page,
            )
            try:
                res = await narajangter_service.search_bids(work_type, params)
            except Exception as exc:  # noqa: BLE001
                print(f"  {work_type:8s} 실패: {type(exc).__name__}: {exc}")
                break
            if not res.items:
                break
            total += len(res.items)
            if notice and any(i.bidNtceNo == notice for i in res.items):
                found_in.append(f"{work_type} p{page}")
            if len(res.items) < 100:
                break
            page += 1
            await asyncio.sleep(0.3)
        print(f"  {work_type:8s} 공고 {total:5d} 건 ({page} 페이지)")

    for label, fn in (
        ("참가가능지역", narajangter_service.get_prtcpt_psbl_rgn_by_date),
        ("면허제한", narajangter_service.get_license_limit_by_date),
    ):
        total = 0
        page = 1
        while True:
            try:
                rows = await fn(bgn, end, page)
            except Exception as exc:  # noqa: BLE001
                print(f"  {label:8s} 실패: {type(exc).__name__}: {exc}")
                break
            if not rows:
                break
            total += len(rows)
            if notice:
                hits = [r for r in rows if r.bidNtceNo == notice]
                for h in hits:
                    detail = getattr(h, "prtcptPsblRgnNm", None) or getattr(
                        h, "lcnsLmtNm", None
                    )
                    found_in.append(f"{label}={detail!r}")
            if len(rows) < NaraJangterService.MAX_PAGE_SIZE:
                break
            page += 1
            await asyncio.sleep(0.3)
        print(f"  {label:8s} {total:5d} 건 ({page} 페이지)")

    if notice:
        if found_in:
            print(f"  ✓ {notice} 검출: {', '.join(found_in)}")
        else:
            print(f"  ✗ {notice} 미검출")


async def resync_day(day: str) -> None:
    """실제 재동기화 (DB 필요)."""
    from app.services.bid_sync_scheduler import bid_sync_scheduler

    # sync_window 는 data_sync_log 를 조회하지 않으므로 skip 없이 항상 수행된다.
    await bid_sync_scheduler.sync_window(f"{day}0000", f"{day}2359")
    print(f"  완료 (data_sync_log 를 {day}0000~{day}2359 로 재마킹)")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("start", help="시작일 YYYYMMDD")
    ap.add_argument("end", nargs="?", help="종료일 YYYYMMDD (생략 시 시작일과 동일)")
    ap.add_argument("--dry-run", action="store_true",
                    help="DB 없이 API 응답 건수만 확인")
    ap.add_argument("--notice", help="이 공고번호가 잡히는지 함께 확인")
    args = ap.parse_args()

    days = daterange(args.start, args.end or args.start)
    mode = "미리보기(DB 미사용)" if args.dry_run else "강제 재동기화"
    print(f"=== {mode}: {days[0]} ~ {days[-1]} ({len(days)}일) ===\n")

    for day in days:
        print(f"[{day}]")
        if args.dry_run:
            await preview_day(day, args.notice)
        else:
            await resync_day(day)
        print()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
