"""한국지역난방공사 입찰정보 조회 서비스.

명세: docs/external-bid-api.md (3. 한국지역난방공사)
실측(2026-10-12): startDate/endDate(YYYYMMDD) 로 조회, XML/UTF-8.
"""

import logging
from typing import Optional

from app.models.external_bid import SOURCE_KDHC
from app.services.external_sources.base import DataGoKrXmlClient
from app.services.external_sources.mapping import (
    NoticeRecord,
    SourceFetch,
    to_dt14,
)
from app.services.external_sources.windows import to_ymd

logger = logging.getLogger(__name__)

AGENCY_NAME = "한국지역난방공사"
BIDDING_URL = "https://apis.data.go.kr/B550373/kdhcbidding2/bidding2"

# 실측(2026-10-12): 이 엔드포인트는 응답이 느려 30s 로는 자주 타임아웃한다.
# 타임아웃은 ExternalApiError 로 올라가 윈도우가 마킹되지 않으므로, 짧게 두면
# 수집이 매 사이클 실패만 반복한다.
TIMEOUT_SECONDS = 60.0


class KdhcSource:
    source = SOURCE_KDHC
    name = AGENCY_NAME
    granularity = "day"

    def __init__(self, client: Optional[DataGoKrXmlClient] = None) -> None:
        self._client = client or DataGoKrXmlClient(timeout=TIMEOUT_SECONDS)

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        params = {
            "startDate": to_ymd(window_start),
            "endDate": to_ymd(window_end),
        }
        context = f"kdhc({params['startDate']}~{params['endDate']})"

        items, calls = await self._client.fetch_paged(
            BIDDING_URL, params, context
        )
        return SourceFetch(
            notices=tuple(self._to_notice(item) for item in items),
            api_calls=calls,
        )

    def _to_notice(self, item: dict) -> NoticeRecord:
        return NoticeRecord(
            source=self.source,
            notice_no=item.get("bidAnnoNo") or "",
            # bidChasu 는 변경차수. 없으면 '00' (지역난방 샘플 기본값).
            notice_ord=item.get("bidChasu") or "00",
            title=item.get("caseNm"),
            # 지역난방은 공고기관명을 주지 않고 담당부서만 준다.
            institution=item.get("gdeptNm") or AGENCY_NAME,
            work_div=item.get("bidGbn"),
            rgst_dt=to_dt14(item.get("regiDt")),
            # bidDt 는 개찰일. 입찰마감일시는 이 API 가 제공하지 않는다.
            openg_dt=to_dt14(item.get("bidDt")),
            status=item.get("status"),
            data=dict(item),
        )


kdhc_source = KdhcSource()
