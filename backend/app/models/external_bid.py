"""외부기관(비-나라장터) 입찰공고 저장 모델.

나라장터용 bid_notices 와 분리한 이유:
  * 공고번호 체계가 기관마다 전혀 다르다 ('305100-26070', 'B3202202182',
    'G022600410' …). 같은 테이블에 넣으면 PK 충돌 위험과 의미 혼선이 생긴다.
  * 대부분의 기관이 참가가능지역/허용업종/추정가격을 제공하지 않는다.
    bid_notices 에 섞으면 지역 필터의 '정보 없음=통과' 탈출구로 모든 지역
    검색에 끼어들고, 업종 필터에서는 반대로 전부 빠져 결과가 왜곡된다.
  * 사정율(bid_reserve_prices) / 북마크 대시보드 파이프라인이 나라장터
    공고 의미에 의존한다.

source 를 PK 선두에 두어 기관 간 공고번호 충돌을 원천 차단한다.
"""

from app.db.database import Base
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

# source 식별자. 어댑터 모듈명과 1:1 로 맞춘다.
SOURCE_LH = "lh"              # 한국토지주택공사
SOURCE_KWATER = "kwater"      # 한국수자원공사
SOURCE_KDHC = "kdhc"          # 한국지역난방공사
SOURCE_KRA = "kra"            # 한국마사회
SOURCE_KOGAS = "kogas"        # 한국가스공사
SOURCE_KEPCO = "kepco"        # 전력개발포털 (한전 + 발전 계열사)

ALL_SOURCES = (
    SOURCE_LH,
    SOURCE_KWATER,
    SOURCE_KDHC,
    SOURCE_KRA,
    SOURCE_KOGAS,
    SOURCE_KEPCO,
)


class ExternalBidNotice(Base):
    """외부기관 입찰공고. 원본 응답은 data(JSONB)에 그대로 보존한다.

    정규화 컬럼은 기관 공통분모만 올린다 — 검색/정렬에 필요한 최소 집합.
    """

    __tablename__ = "external_bid_notices"
    __table_args__ = (
        PrimaryKeyConstraint("source", "notice_no", "notice_ord"),
        Index("ix_external_bid_notices_rgst_dt", "rgst_dt"),
        Index("ix_external_bid_notices_openg_dt", "openg_dt"),
        Index("ix_external_bid_notices_bid_close_dt", "bid_close_dt"),
        # 기관별 최신순 목록 조회가 기본 쿼리 패턴이다.
        Index("ix_external_bid_notices_source_rgst_dt", "source", "rgst_dt"),
    )

    source = Column(String(20), nullable=False)
    notice_no = Column(String(60), nullable=False)
    notice_ord = Column(String(10), nullable=False, default="000")
    title = Column(Text)                  # 공고명
    institution = Column(String(300))     # 공고기관/담당부서
    work_div = Column(String(50))         # 업무구분 (공사/용역/구매/물품)
    cntrct_mthd = Column(String(100))     # 계약방법 (일반경쟁/제한경쟁 …)
    rgst_dt = Column(String(14))          # 공고/등록일시 YYYYMMDDHHMM
    bid_close_dt = Column(String(14))     # 입찰마감일시 YYYYMMDDHHMM
    openg_dt = Column(String(14))         # 개찰일시 YYYYMMDDHHMM
    presmpt_prce = Column(BigInteger)     # 추정가격 (제공하는 기관만)
    status = Column(String(100))          # 진행상태
    data = Column(JSONB, nullable=False)  # 원본 응답 전체
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class ExternalBidResult(Base):
    """외부기관 낙찰/개찰 결과.

    마사회 낙찰정보(API183), 수자원 결과(rstList), 가스공사 SUCCESS_* 필드가
    여기로 들어온다. 한 공고에 복수 행이 올 수 있어 seq 를 PK 에 포함한다.
    """

    __tablename__ = "external_bid_results"
    __table_args__ = (
        PrimaryKeyConstraint("source", "notice_no", "notice_ord", "seq"),
        Index("ix_external_bid_results_openg_dt", "openg_dt"),
    )

    source = Column(String(20), nullable=False)
    notice_no = Column(String(60), nullable=False)
    notice_ord = Column(String(10), nullable=False, default="000")
    seq = Column(Integer, nullable=False, default=0)
    title = Column(Text)
    bidder_nm = Column(String(300))       # 낙찰업체명
    bidder_amt = Column(BigInteger)       # 낙찰금액
    status_nm = Column(String(100))       # 입찰결과구분명
    openg_dt = Column(String(14))         # 개찰/낙찰일시 YYYYMMDDHHMM
    data = Column(JSONB, nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class ExternalSyncLog(Base):
    """외부기관 소스별 동기화 윈도우 기록.

    data_sync_log 와 같은 원칙: **API 호출이 하나라도 실패하면 마킹하지
    않는다.** 마킹해버리면 그 구간이 영구 누락된다.

    window_start/window_end 의 의미는 소스마다 다르다:
      * 대부분: YYYYMMDD0000 ~ YYYYMMDD2359 (일별)
      * kwater: YYYYMM000000 ~ YYYYMM002359 (월별 — searchDt 가 YYYYMM 단위)
      * kepco:  최대 90일 윈도우
    """

    __tablename__ = "external_sync_log"
    __table_args__ = (
        PrimaryKeyConstraint("source", "window_start", "window_end"),
    )

    source = Column(String(20), nullable=False)
    window_start = Column(String(12), nullable=False)
    window_end = Column(String(12), nullable=False)
    total_notices = Column(Integer, default=0)
    total_results = Column(Integer, default=0)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
