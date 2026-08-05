"""특정 공고가 왜 누락됐는지 계층별로 진단합니다.

사용법:
    python scripts/diagnose_missing_notice.py R26BK01665863 000

확인 순서 (위에서부터 끊긴 지점이 원인):
    1. 나라장터 API 가 해당 공고를 반환하는가 (공사/용역)
    2. bid_notices 에 저장돼 있는가
    3. data_sync_log 의 해당 일자 윈도우가 일별(2359)인가 시간별(0059)인가
    4. bid_prtcpt_psbl_rgns / bid_license_limits 부속 데이터가 있는가
       (면허제한이 없으면 업종명 필터 검색에서 완전히 제외됨)
"""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text  # noqa: E402

from app.db.database import AsyncSessionLocal  # noqa: E402
from app.services.narajangter import narajangter_service  # noqa: E402


def _digits(value: str | None) -> str:
    return "".join(c for c in (value or "") if c.isdigit())


async def probe_api(bid_no: str) -> dict | None:
    """공사/용역 목록조회(일반) 엔드포인트로 단건 조회합니다.

    inqryDiv=2 (입찰공고번호) 는 일반 엔드포인트에서만 동작한다.
    PPSSrch 는 bidNtceNo 를 무시하므로 쓰면 안 된다.
    """
    for bid_type in ("cnstwk", "servc"):
        try:
            item = await narajangter_service.get_bid_notice_by_no(bid_no, bid_type)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{bid_type}] 호출 실패: {type(exc).__name__}: {exc}")
            continue
        if item is None:
            print(f"  [{bid_type}] 해당 없음")
            continue
        print(f"  ✓ [{bid_type}] API 에 존재")
        print(f"      bidNtceNm  = {item.bidNtceNm}")
        print(f"      bidNtceOrd = {item.bidNtceOrd}")
        print(f"      rgstDt     = {item.rgstDt}")
        print(f"      opengDt    = {item.opengDt}")
        print(f"      ntceInstt  = {item.ntceInsttNm}")
        return {"bid_type": bid_type, "item": item}
    return None


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    bid_no = sys.argv[1]
    bid_ord = sys.argv[2] if len(sys.argv) > 2 else "000"

    print(f"=== 진단 대상: {bid_no}-{bid_ord} ===\n")

    print("[1] 나라장터 API 단건 조회")
    api_hit = await probe_api(bid_no)
    print()

    async with AsyncSessionLocal() as db:
        print("[2] bid_notices 저장 여부")
        row = (
            await db.execute(
                text(
                    "SELECT bid_ntce_ord, rgst_dt, openg_dt, bid_close_dt, "
                    "       presmpt_prce, fetched_at, data->>'bidNtceNm' AS nm "
                    "FROM bid_notices WHERE bid_ntce_no = :no"
                ),
                {"no": bid_no},
            )
        ).mappings().all()
        if row:
            for r in row:
                print(f"  ord={r['bid_ntce_ord']} rgst_dt={r['rgst_dt']} "
                      f"openg_dt={r['openg_dt']} presmpt={r['presmpt_prce']} "
                      f"fetched_at={r['fetched_at']}")
                print(f"      {r['nm']}")
        else:
            print("  ✗ bid_notices 에 없음 (수집 자체가 안 됨)")
        print()

        # 어느 날짜 윈도우를 봐야 하는지 결정
        day = None
        if row:
            day = (row[0]["rgst_dt"] or "")[:8]
        elif api_hit:
            day = _digits(api_hit["item"].rgstDt)[:8]

        print("[3] data_sync_log 윈도우 상태")
        if not day:
            print("  등록일자를 알 수 없어 생략")
        else:
            logs = (
                await db.execute(
                    text(
                        "SELECT sync_timestamp, window_end, total_notices, "
                        "       total_regions, total_license_limits, synced_at "
                        "FROM data_sync_log "
                        "WHERE sync_timestamp LIKE :pat ORDER BY sync_timestamp"
                    ),
                    {"pat": f"{day}%"},
                )
            ).mappings().all()
            if not logs:
                print(f"  ✗ {day} 에 대한 동기화 기록이 전혀 없음")
            has_daily = False
            for lg in logs:
                kind = "일별" if lg["window_end"].endswith("2359") else "시간별"
                has_daily = has_daily or lg["window_end"].endswith("2359")
                print(f"  {lg['sync_timestamp']}~{lg['window_end']} [{kind}] "
                      f"notices={lg['total_notices']} regions={lg['total_regions']} "
                      f"licenses={lg['total_license_limits']} at={lg['synced_at']}")
            if logs and not has_daily:
                print(f"  ✗ {day} 는 시간별 윈도우만 존재 → 일별 백필이 "
                      f"{day}0000 키 충돌로 영구 skip 됨")
        print()

        print("[4] 부속 데이터")
        rgns = (
            await db.execute(
                text(
                    "SELECT bid_ntce_ord, lmt_sno, prtcpt_psbl_rgn_nm "
                    "FROM bid_prtcpt_psbl_rgns WHERE bid_ntce_no = :no "
                    "ORDER BY lmt_sno"
                ),
                {"no": bid_no},
            )
        ).mappings().all()
        print(f"  참가가능지역: {len(rgns)} 건")
        for r in rgns:
            print(f"      ord={r['bid_ntce_ord']} sno={r['lmt_sno']} "
                  f"{r['prtcpt_psbl_rgn_nm']}")

        lics = (
            await db.execute(
                text(
                    "SELECT bid_ntce_ord, lmt_grp_no, lmt_sno, lcns_lmt_nm, "
                    "       permsn_indstryty_list, indstryty_mfrc_fld_list "
                    "FROM bid_license_limits WHERE bid_ntce_no = :no"
                ),
                {"no": bid_no},
            )
        ).mappings().all()
        print(f"  면허제한: {len(lics)} 건")
        for lc in lics:
            print(f"      ord={lc['bid_ntce_ord']} grp={lc['lmt_grp_no']} "
                  f"sno={lc['lmt_sno']} {lc['lcns_lmt_nm']} "
                  f"| {lc['permsn_indstryty_list']}")
        if row and not lics:
            print("  ! 면허제한 0건 → 업종명 필터 검색에서 '면허정보 없음' "
                  "탈출구로 노출되지만, 업종 매칭 정확도는 떨어짐")
        print()

        print("[5] API 직접 재조회 (부속 데이터)")
        # 부속 데이터 엔드포인트는 공고목록과 달리 inqryDiv=2 + bidNtceNo 필터가
        # 정상 동작하므로 단건 조회가 가능하다.
        try:
            api_rgns = await narajangter_service.get_prtcpt_psbl_rgn_by_bid(
                bid_no, bid_ord
            )
            print(f"  API 참가가능지역: {len(api_rgns)} 건 "
                  f"{[r.prtcptPsblRgnNm for r in api_rgns]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  API 참가가능지역 조회 실패: {exc}")

    print("\n=== 판정 가이드 ===")
    print("  [1] 없음           → API 미제공. 물품/외자 등 미수집 업무구분일 수 있음")
    print("  [1] 있고 [2] 없음  → 수집 누락. 아래로 복구:")
    print("       python scripts/resync_window.py <등록일 YYYYMMDD>")
    print("  [3] 일별(2359) 없음 → 그 날은 일별 백필이 아직 안 돌았음")
    print("  [4] 부속 0건       → 해당 윈도우의 지역/면허 수집이 실패했음")


if __name__ == "__main__":
    asyncio.run(main())
