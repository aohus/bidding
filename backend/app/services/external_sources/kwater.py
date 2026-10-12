"""한국수자원공사 전자입찰 공고(공사/용역) + 결과.

명세: docs/external-bid-api.md (2. 한국수자원공사)
실측(2026-10-12) 주의사항:
  * searchDt 가 **YYYYMM 월 단위**다. 하루짜리 윈도우도 그 달 전체를 조회한다.
  * cntrctDivCd 동작이 엔드포인트마다 다르다:
      - cntrwkList / servcList: **무시된다** (각각 항상 공사/용역만 반환)
      - rstList: **필수**. 생략하면 resultCode 00 에 totalCount 0 으로
        조용히 빈 결과가 온다 → 1~4 를 모두 순회해야 결과가 누락되지 않는다.
  * tndrPblancEnddt 가 값 없을 때 '-' 로 온다 (to_dt14 가 None 처리).
"""

import logging
from collections import Counter
from typing import List, Optional

from app.models.external_bid import SOURCE_KWATER
from app.services.external_sources.base import DataGoKrXmlClient
from app.services.external_sources.mapping import (
    NoticeRecord,
    ResultRecord,
    SourceFetch,
    to_dt14,
    to_int,
)
from app.services.external_sources.windows import month_range

logger = logging.getLogger(__name__)

AGENCY_NAME = "한국수자원공사"
BASE_URL = "https://apis.data.go.kr/B500001/ebid/tndr3"
CNSTWK_URL = f"{BASE_URL}/cntrwkList"
SERVC_URL = f"{BASE_URL}/servcList"
RESULT_URL = f"{BASE_URL}/rstList"

# rstList 전용. 이 코드를 순회하지 않으면 결과가 통째로 0건이 된다.
RESULT_DIV_CODES = ("1", "2", "3", "4")  # 공사 / 용역 / 내자 / 물품


class KwaterSource:
    source = SOURCE_KWATER
    name = AGENCY_NAME
    granularity = "month"

    def __init__(self, client: Optional[DataGoKrXmlClient] = None) -> None:
        self._client = client or DataGoKrXmlClient()

    async def fetch(self, window_start: str, window_end: str) -> SourceFetch:
        notices: List[NoticeRecord] = []
        results: List[ResultRecord] = []
        calls = 0
        # seq 는 공고번호별 일련번호다. div 배치마다 0 부터 다시 세면
        # 같은 공고의 복수 낙찰자가 서로를 덮어쓴다 (PK 에 seq 가 포함됨).
        seq_by_notice: Counter = Counter()

        for month in month_range(window_start, window_end):
            for url, label in ((CNSTWK_URL, "cnstwk"), (SERVC_URL, "servc")):
                items, used = await self._client.fetch_paged(
                    url, {"searchDt": month, "_type": "xml"},
                    f"kwater-{label}({month})",
                )
                calls += used
                notices.extend(self._to_notice(item) for item in items)

            # rstList 는 cntrctDivCd 가 필수다 (생략 시 조용히 0건).
            for div in RESULT_DIV_CODES:
                items, used = await self._client.fetch_paged(
                    RESULT_URL,
                    {"searchDt": month, "_type": "xml", "cntrctDivCd": div},
                    f"kwater-result({month},div={div})",
                )
                calls += used
                for item in items:
                    notice_no = item.get("tndrPbanno") or ""
                    seq = seq_by_notice[notice_no]
                    seq_by_notice[notice_no] += 1
                    results.append(self._to_result(item, seq))

        return SourceFetch(
            notices=tuple(notices),
            results=tuple(results),
            api_calls=calls,
        )

    def _to_notice(self, item: dict) -> NoticeRecord:
        return NoticeRecord(
            source=self.source,
            notice_no=item.get("tndrPbanno") or "",
            notice_ord="000",
            title=item.get("tndrPblancNm"),
            institution=item.get("cntrctDeptNm") or AGENCY_NAME,
            work_div=item.get("cntrctDivNm"),
            cntrct_mthd=item.get("ctrmthdCdNm"),
            rgst_dt=to_dt14(item.get("tndrPblancDe")),
            bid_close_dt=to_dt14(item.get("tndrPblancEnddt")),
            # tndrPlnprc 는 예정가격. 추정가격 컬럼에 올려 금액 정렬에 쓴다.
            presmpt_prce=to_int(item.get("tndrPlnprc")),
            status=item.get("tndrStat"),
            data=dict(item),
        )

    def _to_result(self, item: dict, seq: int) -> ResultRecord:
        return ResultRecord(
            source=self.source,
            notice_no=item.get("tndrPbanno") or "",
            notice_ord="000",
            seq=seq,
            title=item.get("tndrPblancNm"),
            bidder_nm=item.get("entrpsNm"),
            # scsbidAmt 는 '37,086,150' 처럼 쉼표가 들어온다.
            bidder_amt=to_int(item.get("scsbidAmt")),
            status_nm=item.get("cntrctPrgstsNm"),
            openg_dt=to_dt14(item.get("cardPrcsDt")),
            data=dict(item),
        )


kwater_source = KwaterSource()
