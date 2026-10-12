"""전력개발포털 전자입찰 계약정보 (한전 + 발전 계열사).

명세: docs/external-bid-api.md (6. 전력개발포털)
다른 소스와 다른 점:
  * data.go.kr 이 아니라 bigdata.kepco.co.kr 이고, 파라미터명이
    serviceKey 가 아니라 **apiKey**, 전용 키(ELECTRIC_INST_SERVICE_KEY)를 쓴다.
  * **JSON** 응답이고 resultCode 봉투가 없다 — 최상위에 {"data": [...]} 뿐.
  * 페이지네이션이 없다. 윈도우 폭이 응답 크기를 직접 결정한다
    (실측: 12일 전체 계열사 = 399건 / 2.3MB).

이 소스가 한국서부발전(COM02)과 한국중부발전(COM05)을 포함하므로, 각 사의
개별 API 대신 여기로 통합한다 (서부발전 전용 API 는 2026-10-12 기준 HTTP 404).

companyId 는 생략 가능하며, 생략 시 전 계열사를 한 번에 반환한다 (실측:
COM01/02/04/05/06/08/09/10/11/12).
"""

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.models.external_bid import SOURCE_KEPCO
from app.services.external_sources.base import (
    DEFAULT_TIMEOUT_SECONDS,
    ExternalApiError,
)
from app.services.external_sources.mapping import (
    NoticeRecord,
    SourceFetch,
    to_dt14,
    to_int,
)
from app.services.external_sources.windows import to_ymd

logger = logging.getLogger(__name__)

AGENCY_NAME = "전력개발포털"
ELECT_CONTRACT_URL = (
    "https://bigdata.kepco.co.kr/openapi/v1/electContract.do"
)

# 공고시작일~종료일 간격 상한 (명세: 최대 90일).
MAX_WINDOW_DAYS = 90

COMPANY_NAMES = {
    "COM01": "한국전력공사",
    "COM02": "한국서부발전",
    "COM03": "한국전력국제원자력대학원대학교",
    "COM04": "한국남부발전",
    "COM05": "한국중부발전",
    "COM06": "한국남동발전",
    "COM08": "한국동서발전",
    "COM09": "한국전력기술",
    "COM10": "한전KPS",
    "COM11": "한국전력거래소",
    "COM12": "한국원자력연료",
    "COM14": "한국발전교육원",
    "COM16": "한국해상풍력",
    "COM19": "KAPES",
}

# 계약방법/낙찰방법/도급구분 코드 → 명칭 (명세 기준).
COMPETITION_TYPE_NAMES = {
    "Open": "일반경쟁",
    "Destination": "지명경쟁",
    "Limited": "제한경쟁",
    "Private": "수의계약",
}
ITEM_TYPE_NAMES = {
    "Construction": "공사",
    "Service": "용역",
    # 명세의 itemType(도급구분)은 Construction/Service 2종만 적혀 있으나,
    # 실측(2026-10-08, 76건)에서 Product 도 32건 관측됐다. 누락하면
    # work_div 에 번역되지 않은 'Product' 가 그대로 저장된다.
    "Product": "자재구매",
}
PURCHASE_TYPE_NAMES = {
    "Product": "자재구매",
    "ConstructionService": "공사용역",
}
PROGRESS_STATE_NAMES = {
    "PreAttendProgress": "공고진행",
    "AttendProgress": "입찰진행",
    "Close": "마감",
    "Fail": "유찰",
    "OpenTimed": "개찰",
    "Final": "공고종료",
}


def _decode(table: Dict[str, str], code: Optional[str]) -> Optional[str]:
    """코드를 명칭으로 변환합니다. 미등록 코드는 원본을 유지합니다."""
    if not code:
        return None
    return table.get(code, code)


class KepcoSource:
    source = SOURCE_KEPCO
    name = AGENCY_NAME
    granularity = "day"

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        api_key = settings.electric_inst_api_key
        if not api_key:
            raise ExternalApiError(
                "ELECTRIC_INST_SERVICE_KEY 가 설정되지 않았습니다",
                code="CONFIG",
            )

        begin, end = to_ymd(window_start), to_ymd(window_end)
        self._assert_window_width(begin, end)

        params = {
            "apiKey": api_key,
            "noticeBeginDate": begin,
            "noticeEndDate": end,
            "returnType": "json",
            # companyId 생략 = 전 계열사 (실측). 14회 호출을 1회로 줄인다.
        }
        context = f"kepco({begin}~{end})"

        rows = await self._request(params, context)
        return SourceFetch(
            notices=tuple(self._to_notice(row) for row in rows),
            api_calls=1,
        )

    @staticmethod
    def _assert_window_width(begin: str, end: str) -> None:
        """90일 상한을 넘으면 즉시 실패시킵니다.

        API 가 조용히 잘라서 돌려주면 그 구간이 완료 마킹되어 영구 누락된다.
        """
        from datetime import datetime

        span = (
            datetime.strptime(end, "%Y%m%d")
            - datetime.strptime(begin, "%Y%m%d")
        ).days + 1
        if span > MAX_WINDOW_DAYS:
            raise ExternalApiError(
                f"kepco window too wide: {begin}~{end} ({span} days, "
                f"max {MAX_WINDOW_DAYS})",
                code="WINDOW",
            )

    async def _request(
        self, params: Dict[str, Any], context: str
    ) -> Tuple[Dict[str, Any], ...]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(ELECT_CONTRACT_URL, params=params)
        except httpx.HTTPError as exc:
            raise ExternalApiError(
                f"{context}: transport error: {exc}", code="TRANSPORT"
            ) from exc

        if response.status_code == 404:
            logger.info(f"{context}: HTTP 404 → treating as no data")
            return ()
        if response.status_code != 200:
            raise ExternalApiError(
                f"{context}: HTTP {response.status_code}: "
                f"{response.text[:200]}",
                code=str(response.status_code),
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalApiError(
                f"{context}: non-JSON body: {response.text[:200]}",
                code="PARSE",
            ) from exc

        if not isinstance(payload, dict):
            raise ExternalApiError(
                f"{context}: unexpected payload type {type(payload).__name__}",
                code="PARSE",
            )

        rows = payload.get("data")
        if rows is None:
            # 에러를 빈 결과로 삼키면 윈도우가 0건으로 완료 마킹된다.
            raise ExternalApiError(
                f"{context}: response has no 'data' key "
                f"(keys={sorted(payload)[:5]})",
                code="PARSE",
            )
        if not isinstance(rows, list):
            raise ExternalApiError(
                f"{context}: 'data' is not a list", code="PARSE"
            )

        return tuple(row for row in rows if isinstance(row, dict))

    @staticmethod
    def _price(row: Dict[str, Any]) -> Optional[int]:
        """금액을 추정가격 → 추정금액 순으로 취합니다.

        실측(2026-10-12): 두 필드가 구분(purchaseType)에 따라 배타적으로 채워진다.
          * Product(자재구매)          → presumedPrice 만 있음
          * ConstructionService(공사용역) → presumedAmount 만 있음
        폴백하지 않으면 공사용역 공고의 금액이 전부 유실된다.

        주의: 추정금액은 추정가격 + 부가세 등으로 엄밀히는 다른 값이다.
        금액 정렬/필터 용도로는 충분하되, 정확한 추정가격이 필요하면
        data(JSONB) 의 원본 필드를 봐야 한다.
        """
        return to_int(row.get("presumedPrice")) or to_int(
            row.get("presumedAmount")
        )

    def _to_notice(self, row: Dict[str, Any]) -> NoticeRecord:
        company_id = row.get("companyId")
        # placeName(발주기관)이 비면 companyId 로 기관명을 보완한다.
        institution = row.get("placeName") or _decode(
            COMPANY_NAMES, company_id
        )
        work_div = _decode(ITEM_TYPE_NAMES, row.get("itemType")) or _decode(
            PURCHASE_TYPE_NAMES, row.get("purchaseType")
        )
        return NoticeRecord(
            source=self.source,
            notice_no=str(row.get("no") or ""),
            notice_ord="000",
            title=row.get("name"),
            institution=institution,
            work_div=work_div,
            cntrct_mthd=_decode(
                COMPETITION_TYPE_NAMES, row.get("competitionType")
            ),
            rgst_dt=to_dt14(row.get("noticeDate")),
            bid_close_dt=to_dt14(row.get("endDatetime")),
            # 개찰일시 필드가 없다 (개찰방법 openMethod 만 제공).
            presmpt_prce=self._price(row),
            status=_decode(PROGRESS_STATE_NAMES, row.get("progressState")),
            data=dict(row),
        )


kepco_source = KepcoSource()
