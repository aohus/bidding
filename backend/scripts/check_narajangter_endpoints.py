"""앱이 사용하는 BidPublicInfoService02 오퍼레이션 헬스체크.

각 오퍼레이션을 아주 작은 조회(numOfRows=1)로 한 번씩 호출해 OK/FAIL 을 출력한다.
"데이터 없음"(resultCode 03 / HTTP 404)은 엔드포인트가 살아있다는 뜻이므로 OK.
하나라도 FAIL 이면 종료 코드 1. 서비스키는 출력하지 않는다.

사용법:
    python scripts/check_narajangter_endpoints.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

import httpx

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.narajangter import NaraJangterService, narajangter_service  # noqa: E402
from app.services.service_key_rotator import redact_service_key  # noqa: E402

PROBE_BID_NO = "R00000000000"  # inqryDiv=2 전용 오퍼레이션용 (존재하지 않는 번호여도 OK)
SERVICE = NaraJangterService


def _by_date(extra: dict | None = None):
    def build(now: datetime) -> dict:
        return {
            "inqryDiv": "1",
            "inqryBgnDt": (now - timedelta(hours=1)).strftime("%Y%m%d%H%M"),
            "inqryEndDt": now.strftime("%Y%m%d%H%M"),
            **(extra or {}),
        }
    return build


def _by_bid(extra: dict | None = None):
    def build(now: datetime) -> dict:
        return {"inqryDiv": "2", "bidNtceNo": PROBE_BID_NO, **(extra or {})}
    return build


# (오퍼레이션명, URL, 파라미터 빌더)
OPERATIONS = [
    ("getBidPblancListInfoCnstwkPPSSrch02", SERVICE.BASE_CNST_URL, _by_date()),
    ("getBidPblancListInfoServcPPSSrch02", SERVICE.BASE_SERV_URL, _by_date()),
    ("getBidPblancListInfoCnstwk02", SERVICE.PLAIN_CNST_URL, _by_bid()),
    ("getBidPblancListInfoServc02", SERVICE.PLAIN_SERV_URL, _by_bid()),
    ("getBidPblancListInfoCnstwkBsisAmount02", SERVICE.CNSTWK_BSSAMT_URL, _by_bid()),
    ("getBidPblancListInfoServcBsisAmount02", SERVICE.SERVC_BSSAMT_URL, _by_bid()),
    ("getBidPblancListInfoPrtcptPsblRgn02", SERVICE.PRTCPT_PSBL_RGN_URL, _by_date()),
    ("getBidPblancListInfoLicenseLimit02", SERVICE.LICENSE_LIMIT_URL, _by_date()),
    ("getBidPblancListInfoAtchFileInfo02", SERVICE.ATCH_FILE_URL, _by_date({"bsnsDivCd": "3"})),
    ("getBidPblancListInfoEorderAtchFileInfo02", SERVICE.EORDER_ATCH_FILE_URL, _by_date()),
    ("getBidPblancIncntvRgnListInfo02", SERVICE.INCNTV_RGN_URL, _by_date()),
    ("getBidPblancJntcontrctDutyRgnListInfo02", SERVICE.JNTCONTRCT_DUTY_RGN_URL, _by_date()),
    ("getBidPblancSubsiCnsttyIndstrytyListInfo02", SERVICE.SUBSI_CNSTTY_URL, _by_date()),
]


def redact(message: str, keys: list[str]) -> str:
    """에러 문구에 섞였을 수 있는 서비스키를 가린다 (공용 헬퍼에 위임)."""
    return redact_service_key(message, keys)


async def check_operation(name: str, url: str, build_params, now: datetime) -> tuple[bool, str]:
    params = {"numOfRows": 1, "pageNo": 1, "type": "json", **build_params(now)}
    try:
        async with httpx.AsyncClient(timeout=SERVICE.DEFAULT_TIMEOUT_SECONDS) as client:
            data = await narajangter_service._request(client, url, params, f"check:{name}")
    except Exception as exc:  # noqa: BLE001
        keys = list(getattr(narajangter_service, "_service_keys", []) or [])
        return False, redact(f"{type(exc).__name__}: {exc}", keys)
    if data is None:
        return True, "OK (no data)"
    code = (data.get("response", {}).get("header", {}) or {}).get("resultCode", "?")
    return True, f"OK (resultCode={code})"


async def main() -> int:
    now = datetime.now()
    failures = 0
    for name, url, build in OPERATIONS:
        ok, detail = await check_operation(name, url, build, now)
        print(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}")
        failures += 0 if ok else 1
        await asyncio.sleep(0.3)
    print(f"\n{len(OPERATIONS) - failures}/{len(OPERATIONS)} OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
