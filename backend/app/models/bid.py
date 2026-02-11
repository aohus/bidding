import uuid

from app.db.database import Base
from sqlalchemy import Column, DateTime, Index, Integer, PrimaryKeyConstraint, String, BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func


class BidNotice(Base):
    """입찰공고 데이터 - API에서 가져온 공고 정보를 DB에 저장"""
    __tablename__ = "bid_notices"
    __table_args__ = (
        Index('ix_bid_notices_rgst_dt', 'rgst_dt'),
        Index('ix_bid_notices_openg_dt', 'openg_dt'),
        Index('ix_bid_notices_bid_close_dt', 'bid_close_dt'),
    )

    bid_ntce_no = Column(String(50), primary_key=True)
    bid_ntce_ord = Column(String(10), primary_key=True)
    rgst_dt = Column(String(14))         # 등록일시 normalized YYYYMMDDHHMM
    openg_dt = Column(String(14))        # 개찰일시 normalized YYYYMMDDHHMM
    bid_close_dt = Column(String(14))    # 입찰마감일시 normalized YYYYMMDDHHMM
    presmpt_prce = Column(BigInteger)    # 추정가격 (숫자)
    main_cnsty_nm = Column(String(200))  # 주공종명
    data = Column(JSONB, nullable=False) # 전체 BidItem 데이터
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class BidBasisAmount(Base):
    """기초금액 정보 (공사/용역)"""
    __tablename__ = "bid_basis_amounts"

    bid_ntce_no = Column(String(50), primary_key=True)
    bid_ntce_ord = Column(String(10), primary_key=True, default="000")
    bid_type = Column(String(10), primary_key=True)  # 'cnstwk' or 'servc'
    data = Column(JSONB, nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class BidPrtcptPsblRgn(Base):
    """참가가능지역 정보"""
    __tablename__ = "bid_prtcpt_psbl_rgns"

    bid_ntce_no = Column(String(50), primary_key=True)
    bid_ntce_ord = Column(String(10), primary_key=True)
    lmt_sno = Column(Integer, primary_key=True)
    prtcpt_psbl_rgn_nm = Column(String(200), index=True)
    rgst_dt = Column(String(30))
    bsns_div_nm = Column(String(50))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class UserLocation(Base):
    """사용자 소재지 정보"""
    __tablename__ = "user_locations"

    location_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    location_name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BidOpeningResult(Base):
    """개찰결과 데이터 캐시"""
    __tablename__ = "bid_opening_results"

    bid_ntce_no = Column(String(50), primary_key=True)
    data = Column(JSONB, nullable=False)  # 전체 개찰결과 리스트
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class BidLicenseLimit(Base):
    """면허제한 정보 - 허용업종 필터링용"""
    __tablename__ = "bid_license_limits"
    __table_args__ = (
        PrimaryKeyConstraint("bid_ntce_no", "bid_ntce_ord", "lmt_grp_no", "lmt_sno"),
    )

    bid_ntce_no = Column(String(50), nullable=False)
    bid_ntce_ord = Column(String(10), nullable=False, default="000")
    lmt_grp_no = Column(String(10), nullable=False)
    lmt_sno = Column(String(10), nullable=False)
    lcns_lmt_nm = Column(String(500), nullable=True)
    permsn_indstryty_list = Column(Text, nullable=True, index=True)
    bsns_div_nm = Column(String(30), nullable=True)
    rgst_dt = Column(String(30), nullable=True)
    indstryty_mfrc_fld_list = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class DataSyncLog(Base):
    """데이터 동기화 로그 - 시간 윈도우 기반 동기화 추적

    sync_timestamp: 윈도우 시작 (YYYYMMDDHH00)
    window_end: 윈도우 끝 (YYYYMMDDHH59 또는 YYYYMMDD2359)
    - 시간별: 202602111300 ~ 202602111359
    - 일별 백필: 202602100000 ~ 202602102359
    """
    __tablename__ = "data_sync_log"

    sync_timestamp = Column(String(12), primary_key=True)
    window_end = Column(String(12), nullable=False)
    total_notices = Column(Integer, default=0)
    total_regions = Column(Integer, default=0)
    total_license_limits = Column(Integer, default=0)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
