"""한국토지주택공사(LH) 입찰공고정보.

명세: docs/external-bid-api.md (1. 한국토지주택공사)
실측(2026-10-12) 주의사항:
  * 응답이 **EUC-KR** 이다 (다른 소스는 UTF-8).
  * <body><item> 구조로 **<items> 래퍼가 없다**.
  * 필드가 ~170개로 가장 풍부하다. 지역제한(zoneRstrct1~4)과
    면허/업종(req1~10Reqlic1~10Nm)까지 제공하는 유일한 외부 소스다 —
    원본은 data(JSONB)에 전부 보존하므로 추후 필터 연동이 가능하다.
"""

import logging
from typing import Optional

from app.models.external_bid import SOURCE_LH
from app.services.external_sources.base import DataGoKrXmlClient
from app.services.external_sources.mapping import (
    NoticeRecord,
    SourceFetch,
    to_dt14,
    to_int,
)
from app.services.external_sources.windows import to_ymd

logger = logging.getLogger(__name__)

AGENCY_NAME = "한국토지주택공사"
OPEN_BID_URL = (
    "https://apis.data.go.kr/B552555/OpenBidInfoList/getOpenBidInfo"
)


class LhSource:
    source = SOURCE_LH
    name = AGENCY_NAME
    granularity = "day"

    def __init__(self, client: Optional[DataGoKrXmlClient] = None) -> None:
        self._client = client or DataGoKrXmlClient()

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        params = {
            "tndrbidRegDtStart": to_ymd(window_start),
            "tndrbidRegDtEnd": to_ymd(window_end),
        }
        context = (
            f"lh({params['tndrbidRegDtStart']}~{params['tndrbidRegDtEnd']})"
        )

        items, calls = await self._client.fetch_paged(
            OPEN_BID_URL, params, context
        )
        return SourceFetch(
            notices=tuple(self._to_notice(item) for item in items),
            api_calls=calls,
        )

    def _to_notice(self, item: dict) -> NoticeRecord:
        return NoticeRecord(
            source=self.source,
            notice_no=item.get("bidNum") or "",
            notice_ord=item.get("bidDegree") or "00",
            title=item.get("bidnmKor"),
            # zoneHqCd 는 코드가 아니라 지역본부명이 들어온다 (실측).
            institution=item.get("zoneHqCd") or AGENCY_NAME,
            work_div=item.get("cstrtnJobGbNm"),
            cntrct_mthd=item.get("tndrCtrctMedCd"),
            rgst_dt=to_dt14(item.get("tndrbidRegDt")),
            # 입찰서 접수마감일시를 입찰마감으로 본다.
            bid_close_dt=to_dt14(item.get("tndrdocAcptEndDtm")),
            openg_dt=to_dt14(item.get("openDtm")),
            presmpt_prce=to_int(item.get("presmtPrc")),
            status=item.get("bidProgrsStatus"),
            data=dict(item),
        )


lh_source = LhSource()
