"""한국가스공사 입찰정보.

명세: docs/external-bid-api.md (5. 한국가스공사)
실측(2026-10-12): DOCDATE_START/END(YYYYMMDD) 로 조회. 필드명이 전부
대문자+언더스코어다. 공고와 낙찰결과(SUCCESS_*)가 **같은 행**에 온다.
"""

import logging
from typing import List, Optional

from app.models.external_bid import SOURCE_KOGAS
from app.services.external_sources.base import DataGoKrXmlClient
from app.services.external_sources.mapping import (
    NoticeRecord,
    ResultRecord,
    SourceFetch,
    to_dt14,
    to_int,
)
from app.services.external_sources.windows import to_ymd

logger = logging.getLogger(__name__)

AGENCY_NAME = "한국가스공사"
BID_INFO_URL = (
    "https://apis.data.go.kr/B551210/bidInfoList2/getBidInfoList2"
)

STATUS_CANCELLED = "취소"
STATUS_AWARDED = "낙찰"


class KogasSource:
    source = SOURCE_KOGAS
    name = AGENCY_NAME
    granularity = "day"

    def __init__(self, client: Optional[DataGoKrXmlClient] = None) -> None:
        self._client = client or DataGoKrXmlClient()

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        params = {
            "DOCDATE_START": to_ymd(window_start),
            "DOCDATE_END": to_ymd(window_end),
        }
        context = (
            f"kogas({params['DOCDATE_START']}~{params['DOCDATE_END']})"
        )

        items, calls = await self._client.fetch_paged(
            BID_INFO_URL, params, context
        )

        notices: List[NoticeRecord] = []
        results: List[ResultRecord] = []
        for item in items:
            notices.append(self._to_notice(item))
            result = self._to_result(item)
            if result is not None:
                results.append(result)

        return SourceFetch(
            notices=tuple(notices),
            results=tuple(results),
            api_calls=calls,
        )

    @staticmethod
    def _status(item: dict) -> Optional[str]:
        """진행상태를 도출합니다. 가스공사는 상태 필드를 직접 주지 않는다."""
        if item.get("CANCEL_YN"):
            return STATUS_CANCELLED
        if item.get("SUCCESS_CORP_NAME"):
            return STATUS_AWARDED
        return None

    def _to_notice(self, item: dict) -> NoticeRecord:
        return NoticeRecord(
            source=self.source,
            notice_no=item.get("NOTICE_CODE") or "",
            notice_ord="000",
            title=item.get("NOTICE_NAME"),
            # 공고부서를 주지 않으므로 기관명을 쓴다.
            institution=AGENCY_NAME,
            work_div=item.get("WORK_TYPE_NAME"),
            cntrct_mthd=item.get("CONT_METHOD_NAME"),
            rgst_dt=to_dt14(item.get("NOTICE_DT")),
            bid_close_dt=to_dt14(item.get("END_DT")),
            openg_dt=to_dt14(item.get("OPEN_DT")),
            status=self._status(item),
            data=dict(item),
        )

    def _to_result(self, item: dict) -> Optional[ResultRecord]:
        """낙찰업체가 있는 행만 결과 레코드를 만듭니다."""
        bidder = item.get("SUCCESS_CORP_NAME")
        if not bidder:
            return None
        return ResultRecord(
            source=self.source,
            notice_no=item.get("NOTICE_CODE") or "",
            notice_ord="000",
            seq=0,
            title=item.get("NOTICE_NAME"),
            bidder_nm=bidder,
            bidder_amt=to_int(item.get("SUCCESS_AMT")),
            status_nm=STATUS_AWARDED,
            openg_dt=to_dt14(item.get("SUCCESS_DT") or item.get("OPEN_DT")),
            data=dict(item),
        )


kogas_source = KogasSource()
