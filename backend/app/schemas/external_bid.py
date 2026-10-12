"""외부기관 공고 조회 응답 스키마.

나라장터 BidItem 과 **의도적으로 분리**한다. 기관마다 제공 필드가 달라
BidItem 모양에 억지로 맞추면 대부분이 null 인 가짜 호환이 된다.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ExternalBidItem(BaseModel):
    source: str                        # 기관 식별자 (lh/kwater/kdhc/kra/kogas/kepco)
    sourceName: str                    # 기관명 (한글)
    noticeNo: str                      # 공고번호
    noticeOrd: str                     # 차수
    title: Optional[str] = None        # 공고명
    institution: Optional[str] = None  # 공고기관/담당부서
    workDiv: Optional[str] = None      # 업무구분
    cntrctMthd: Optional[str] = None   # 계약방법
    rgstDt: Optional[str] = None       # 공고/등록일시 YYYYMMDDHHMM
    bidCloseDt: Optional[str] = None   # 입찰마감일시
    opengDt: Optional[str] = None      # 개찰일시
    presmptPrce: Optional[int] = None  # 추정가격
    status: Optional[str] = None       # 진행상태
    raw: Dict[str, Any] = {}           # 원본 응답 (기관별 고유 필드 전체)


class ExternalBidListResponse(BaseModel):
    items: List[ExternalBidItem]
    totalCount: int
    numOfRows: int
    pageNo: int


class ExternalBidResultItem(BaseModel):
    source: str
    sourceName: str
    noticeNo: str
    noticeOrd: str
    seq: int
    title: Optional[str] = None
    bidderNm: Optional[str] = None     # 낙찰업체명
    bidderAmt: Optional[int] = None    # 낙찰금액
    statusNm: Optional[str] = None     # 결과구분명
    opengDt: Optional[str] = None
    raw: Dict[str, Any] = {}


class ExternalBidResultListResponse(BaseModel):
    items: List[ExternalBidResultItem]
    totalCount: int
    numOfRows: int
    pageNo: int


class ExternalSourceInfo(BaseModel):
    source: str
    name: str
    granularity: str


class ExternalSourceListResponse(BaseModel):
    sources: List[ExternalSourceInfo]
