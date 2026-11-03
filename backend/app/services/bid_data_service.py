import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

KST = timezone(timedelta(hours=9))

from sqlalchemy import BigInteger, and_, cast, exists, func, nullslast, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.bid import (
    BidAttachment as BidAttachmentCache,
    BidBasisAmount,
    BidIncntvRgn,
    BidJntcontrctDutyRgn,
    BidLicenseLimit,
    BidNotice,
    BidPrtcptPsblRgn,
    BidReservePrice,
    BidSubsiCnstty,
    DataSyncLog,
    UserLocation,
)
from app.schemas.bid import (
    BidApiResponse,
    BidAValueItem,
    BidItem,
    BidSearchParams,
    IncntvRgnItem,
    JntcontrctDutyRgnItem,
    LicenseLimitItem,
    PrtcptPsblRgnItem,
    SubsiCnsttyInfo,
    SubsiCnsttyItem,
)

logger = logging.getLogger(__name__)

ATTACHMENT_CACHE_TTL = timedelta(hours=24)
ATTACHMENT_EMPTY_CACHE_TTL = timedelta(hours=1)
ATTACHMENT_FAILED_CACHE_TTL = timedelta(minutes=10)  # API 오류 시 네거티브 캐시
ATTACHMENT_KIND_API = "api"
ATTACHMENT_KIND_LEGACY = "legacy"  # API 정상 + 빈 결과 -> 레거시 URL 폴백
ATTACHMENT_KIND_FAILED = "failed"  # API 오류 -> 레거시 URL 폴백
DEFAULT_BID_ORD = "000"


def normalize_date_str(date_str: Optional[str]) -> str:
    """Normalize date string to YYYYMMDDHHMM format for DB comparison."""
    if not date_str:
        return ""
    cleaned = "".join(c for c in date_str if c.isdigit())
    if len(cleaned) >= 12:
        return cleaned[:12]
    return cleaned.ljust(12, "0")


def parse_price(price_str: Optional[str]) -> int:
    """Parse price string to integer."""
    if not price_str:
        return 0
    try:
        return int(float(price_str))
    except (ValueError, TypeError):
        return 0


def escape_like(term: str) -> str:
    """LIKE/ILIKE 패턴에서 사용자 입력의 와일드카드를 리터럴로 이스케이프합니다.

    '%', '_', '\\' 를 그대로 검색어로 취급하기 위함. escape='\\' 와 함께 사용.
    """
    return (
        term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


def get_matching_regions(location_name: str) -> List[str]:
    """소재지에서 참가가능지역 매칭 패턴을 생성합니다.

    예: "경기도 성남시" → ["전체", "", "경기도", "경기도 성남시"]
    """
    parts = location_name.split()
    regions = ["전체", ""]
    current = ""
    for part in parts:
        current = f"{current} {part}".strip()
        regions.append(current)
    return regions


def location_matches(region_name: Optional[str], location_name: str) -> bool:
    """get_matching_regions + 하위 지역 LIKE 규칙과 동일한 지역 매칭 (Python 판정용)."""
    if not region_name:
        return False
    return (
        region_name in get_matching_regions(location_name)
        or region_name.startswith(f"{location_name} ")
    )


def _parse_sno(value: Optional[str], fallback: int = 0) -> int:
    """sno 를 정수로. 파싱 불가/누락 시 페이지 내 1-based 인덱스(fallback)를 쓴다.

    예전에는 0 으로 수렴해 같은 공고의 여러 행이 PK 충돌로 하나로 합쳐졌다.
    """
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        logger.debug(f"unparsable sno {value!r}, using page index {fallback}")
        return fallback


def _region_exists(model, name_col, location_name: str):
    """소재지와 매칭되는 부속 지역 행이 있는 공고 EXISTS 조건 (파라미터 바인딩)."""
    exact = [r for r in get_matching_regions(location_name) if r]
    return exists(
        select(model.bid_ntce_no).where(
            model.bid_ntce_no == BidNotice.bid_ntce_no,
            model.bid_ntce_ord == BidNotice.bid_ntce_ord,
            or_(
                name_col.in_(exact),
                name_col.like(f"{escape_like(location_name)} %", escape="\\"),
            ),
        )
    )


class BidDataService:
    """DB 기반 입찰 데이터 서비스"""

    async def search_from_db(
        self,
        db: AsyncSession,
        params: BidSearchParams,
        user_id=None,
        *,
        created_after: Optional[datetime] = None,
        order_by_created_at: bool = False,
    ) -> BidApiResponse:
        """DB에서 입찰공고를 검색합니다.

        created_after: 지정 시 BidNotice.created_at(최초 삽입 시각) > 값 인 공고만.
            알림처럼 "내가 아직 못 본 공고" 를 rgst_dt 와 무관하게 찾을 때 사용.
        order_by_created_at: True 면 created_at 오름차순 (params.orderBy 무시).
        """
        query = select(BidNotice)
        if created_after is not None:
            query = query.where(BidNotice.created_at > created_after)

        # 날짜 범위 필터
        if params.inqryDiv == "1":
            query = query.where(BidNotice.rgst_dt >= params.inqryBgnDt)
            query = query.where(BidNotice.rgst_dt <= params.inqryEndDt)
        else:
            query = query.where(BidNotice.openg_dt >= params.inqryBgnDt)
            query = query.where(BidNotice.openg_dt <= params.inqryEndDt)

        # 참가가능지역 필터 (소재지 기준)
        needs_region_join = False
        region_conditions = []
        like_conditions = []  # 하위 지역 LIKE 매칭용

        location = (
            await self.get_user_location(db, user_id) if user_id else None
        )
        location_name = location.location_name if location else None

        if params.useLocationFilter and user_id:
            if location:
                matching = get_matching_regions(location.location_name)
                region_conditions = matching
                # 소재지의 마지막(가장 구체적) 지역으로 하위 LIKE 매칭
                like_conditions = [location.location_name]
                needs_region_join = True
        elif params.prtcptLmtRgnNm:
            regions = [r.strip() for r in params.prtcptLmtRgnNm.split(",")]
            region_conditions = ["전체", ""] + regions
            like_conditions = regions  # 하위 지역도 매칭
            needs_region_join = True

        if needs_region_join and region_conditions:
            RgnAlias = aliased(BidPrtcptPsblRgn)
            no_region = ~exists(
                select(RgnAlias.bid_ntce_no).where(
                    RgnAlias.bid_ntce_no == BidNotice.bid_ntce_no,
                    RgnAlias.bid_ntce_ord == BidNotice.bid_ntce_ord,
                )
            )
            region_match_conds = [
                RgnAlias.prtcpt_psbl_rgn_nm.in_(region_conditions),
            ]
            for rgn in like_conditions:
                region_match_conds.append(
                    RgnAlias.prtcpt_psbl_rgn_nm.like(f"{rgn} %")
                )
            has_matching_region = exists(
                select(RgnAlias.bid_ntce_no).where(
                    RgnAlias.bid_ntce_no == BidNotice.bid_ntce_no,
                    RgnAlias.bid_ntce_ord == BidNotice.bid_ntce_ord,
                    or_(*region_match_conds),
                )
            )
            query = query.where(or_(no_region, has_matching_region))

        # 가산지역 / 공동도급의무지역 필터 (소재지 미등록 시 무시)
        for flag, label, model, col in (
            (params.incntvRgnOnly, "incntvRgnOnly", BidIncntvRgn,
             BidIncntvRgn.incntv_rgn_nm),
            (params.jntcontrctDutyRgnOnly, "jntcontrctDutyRgnOnly",
             BidJntcontrctDutyRgn, BidJntcontrctDutyRgn.jntcontrct_duty_rgn_nm),
        ):
            if not flag:
                continue
            if not location_name:
                logger.info(
                    f"{label} ignored: user has no registered location"
                )
                continue
            query = query.where(_region_exists(model, col, location_name))

        # 업종명 필터 (면허제한명 + 허용업종목록 기반, EXISTS)
        # 엄격 필터: 지정한 업종에 매칭되는 공고만 남긴다. 허용업종 정보가
        # 아예 없는 공고는 결과에서 제외한다. (참가가능지역 필터는 "전체"
        # sentinel 행이 실제로 존재해 탈출구가 정상 동작하지만, 면허제한은
        # 정보 없는 공고에 행 자체가 없어 탈출구가 "정보 없음=모두 통과"로
        # 새기 때문에 업종 필터에서는 탈출구를 두지 않는다.)
        industries = [
            i.strip() for i in (params.indstrytyNm or "").split(",") if i.strip()
        ]
        if industries:
            LicAlias = aliased(BidLicenseLimit)
            industry_conditions = []
            for ind in industries:
                pattern = f"%{escape_like(ind)}%"
                industry_conditions.append(
                    LicAlias.lcns_lmt_nm.ilike(pattern, escape="\\")
                )
                industry_conditions.append(
                    LicAlias.permsn_indstryty_list.ilike(pattern, escape="\\")
                )
            has_matching_industry = exists(
                select(LicAlias.bid_ntce_no).where(
                    LicAlias.bid_ntce_no == BidNotice.bid_ntce_no,
                    LicAlias.bid_ntce_ord == BidNotice.bid_ntce_ord,
                    or_(*industry_conditions),
                )
            )
            if params.includeSubsiCnstty:
                SubAlias = aliased(BidSubsiCnstty)
                subsi_conditions = [
                    SubAlias.subsi_cnstty_nm.ilike(
                        f"%{escape_like(ind)}%", escape="\\"
                    )
                    for ind in industries
                ]
                has_matching_subsi = exists(
                    select(SubAlias.bid_ntce_no).where(
                        SubAlias.bid_ntce_no == BidNotice.bid_ntce_no,
                        SubAlias.bid_ntce_ord == BidNotice.bid_ntce_ord,
                        or_(*subsi_conditions),
                    )
                )
                query = query.where(
                    or_(has_matching_industry, has_matching_subsi)
                )
            else:
                query = query.where(has_matching_industry)

        # 추정가격 범위 필터
        if params.presmptPrceBgn:
            price_bgn = parse_price(params.presmptPrceBgn)
            if price_bgn > 0:
                query = query.where(BidNotice.presmpt_prce >= price_bgn)
        if params.presmptPrceEnd:
            price_end = parse_price(params.presmptPrceEnd)
            if price_end > 0:
                query = query.where(BidNotice.presmpt_prce <= price_end)

        # 입찰마감 제외
        if params.bidClseExcpYn == "Y":
            now_str = datetime.now().strftime("%Y%m%d%H%M")
            query = query.where(BidNotice.bid_close_dt > now_str)

        # 공사현장지역명 필터
        if params.cnstrtsiteRgnNm:
            query = query.where(
                BidNotice.data["cnstrtsiteRgnNm"].astext.ilike(
                    f"%{params.cnstrtsiteRgnNm}%"
                )
            )

        # 전체 건수 조회
        count_query = select(func.count()).select_from(
            query.with_only_columns(BidNotice.bid_ntce_no).subquery()
        )
        total_result = await db.execute(count_query)
        total_count = total_result.scalar() or 0

        # 정렬
        order_columns = {
            "rgstDt": BidNotice.rgst_dt,
            "bidClseDt": BidNotice.bid_close_dt,
            "presmptPrce": BidNotice.presmpt_prce,
            "bdgtAmt": cast(
                func.nullif(BidNotice.data["bdgtAmt"].astext, ""),
                BigInteger,
            ),
        }
        order_col = order_columns.get(params.orderBy or "")
        if order_by_created_at:
            query = query.order_by(
                BidNotice.created_at.asc(), BidNotice.bid_ntce_no.asc(),
                BidNotice.bid_ntce_ord.asc(),
            )
        elif order_col is not None:
            if params.orderDir == "asc":
                query = query.order_by(nullslast(order_col.asc()))
            else:
                query = query.order_by(nullslast(order_col.desc()))
        else:
            query = query.order_by(BidNotice.rgst_dt.desc())
        offset = (params.pageNo - 1) * params.numOfRows
        query = query.offset(offset).limit(params.numOfRows)

        result = await db.execute(query)
        notices = result.scalars().all()

        items = await self.enrich_notices(db, notices, location_name)

        return BidApiResponse(
            items=items,
            totalCount=total_count,
            numOfRows=params.numOfRows,
            pageNo=params.pageNo,
        )

    async def max_created_at(
        self, db: AsyncSession, keys: List[tuple]
    ) -> Optional[datetime]:
        """주어진 (공고번호, 차수) 들 중 가장 늦은 created_at (알림 커서용)."""
        if not keys:
            return None
        result = await db.execute(
            select(func.max(BidNotice.created_at)).where(
                tuple_(BidNotice.bid_ntce_no, BidNotice.bid_ntce_ord).in_(keys)
            )
        )
        return result.scalar()

    async def enrich_notices(
        self,
        db: AsyncSession,
        notices: list,
        location_name: Optional[str] = None,
    ) -> List[BidItem]:
        """공고 행에 지역/업종/가산지역/공동도급의무지역/부공종 정보를 붙여 BidItem 으로 변환.

        search_from_db 와 상세 조회가 공통으로 사용한다. 조회는 모두 배치 쿼리.
        location_name 이 None 이면 isIncntvRgnMatch/isJntcontrctDutyRgnMatch 는 None.
        """
        if not notices:
            return []
        bid_nos = list({n.bid_ntce_no for n in notices})
        pairs = list({(n.bid_ntce_no, n.bid_ntce_ord) for n in notices})

        # 참가가능지역 — sort + dedup 으로 결정적 직렬화
        # (estimate_rate 그룹 키와 동일한 형태여야 매칭됨)
        rgn_query = select(
            BidPrtcptPsblRgn.bid_ntce_no,
            BidPrtcptPsblRgn.prtcpt_psbl_rgn_nm,
        ).where(
            BidPrtcptPsblRgn.bid_ntce_no.in_(bid_nos)
        )
        rgn_result = await db.execute(rgn_query)
        rgn_rows = rgn_result.all()

        rgn_map: dict[str, list[str]] = {}
        for row in rgn_rows:
            if row[1]:
                rgn_map.setdefault(row[0], []).append(row[1])
        for k in rgn_map:
            rgn_map[k] = sorted(set(rgn_map[k]))

        # 면허제한명 + 허용업종목록 + 주력분야 — sort + dedup 으로 결정적 직렬화
        lic_query = select(
            BidLicenseLimit.bid_ntce_no,
            BidLicenseLimit.lcns_lmt_nm,
            BidLicenseLimit.permsn_indstryty_list,
            BidLicenseLimit.indstryty_mfrc_fld_list,
        ).where(
            BidLicenseLimit.bid_ntce_no.in_(bid_nos)
        )
        lic_result = await db.execute(lic_query)
        lic_rows = lic_result.all()

        lic_map: dict[str, list[str]] = {}
        mfrc_map: dict[str, list[str]] = {}
        for row in lic_rows:
            bid_no = row[0]
            # lcns_lmt_nm: "조경식재ㆍ시설물공사업/4993" → "조경식재ㆍ시설물공사업"
            if row[1]:
                name = row[1].rsplit("/", 1)[0] if "/" in row[1] else row[1]
                lic_map.setdefault(bid_no, []).append(name)
            elif row[2]:
                lic_map.setdefault(bid_no, []).append(row[2])
            # indstryty_mfrc_fld_list: "[1^철근·콘크리트공사]" → "철근·콘크리트공사"
            if row[3]:
                raw = row[3].strip("[]")
                fields = [f for f in raw.split("^") if f and not f.isdigit()]
                for f in fields:
                    mfrc_map.setdefault(bid_no, []).append(f)
        for k in lic_map:
            lic_map[k] = sorted(set(lic_map[k]))
        for k in mfrc_map:
            mfrc_map[k] = sorted(set(mfrc_map[k]))

        incntv_rows = (await db.execute(
            select(
                BidIncntvRgn.bid_ntce_no,
                BidIncntvRgn.bid_ntce_ord,
                BidIncntvRgn.incntv_rgn_nm,
            ).where(
                tuple_(BidIncntvRgn.bid_ntce_no, BidIncntvRgn.bid_ntce_ord).in_(pairs)
            )
        )).all()
        jnt_rows = (await db.execute(
            select(
                BidJntcontrctDutyRgn.bid_ntce_no,
                BidJntcontrctDutyRgn.bid_ntce_ord,
                BidJntcontrctDutyRgn.jntcontrct_duty_rgn_nm,
                BidJntcontrctDutyRgn.rgn_duty_jntcontrct_rt,
            ).where(
                tuple_(
                    BidJntcontrctDutyRgn.bid_ntce_no,
                    BidJntcontrctDutyRgn.bid_ntce_ord,
                ).in_(pairs)
            )
        )).all()
        subsi_rows = (await db.execute(
            select(
                BidSubsiCnstty.bid_ntce_no,
                BidSubsiCnstty.bid_ntce_ord,
                BidSubsiCnstty.sno,
                BidSubsiCnstty.subsi_cnstty_nm,
                BidSubsiCnstty.subsi_cnstty_indstryty_evl_rt,
            ).where(
                tuple_(BidSubsiCnstty.bid_ntce_no, BidSubsiCnstty.bid_ntce_ord).in_(pairs)
            )
        )).all()

        incntv_map: dict[tuple, list[str]] = {}
        for no, ord_, nm in incntv_rows:
            if nm:
                incntv_map.setdefault((no, ord_), []).append(nm)
        jnt_map: dict[tuple, list[str]] = {}
        jnt_rate: dict[tuple, str] = {}
        for no, ord_, nm, rt in jnt_rows:
            if nm:
                jnt_map.setdefault((no, ord_), []).append(nm)
            if rt and (no, ord_) not in jnt_rate:
                jnt_rate[(no, ord_)] = rt
        subsi_map: dict[tuple, list[tuple]] = {}
        for no, ord_, sno, nm, rt in subsi_rows:
            if nm:
                subsi_map.setdefault((no, ord_), []).append((sno or 0, nm, rt))

        items: List[BidItem] = []
        for notice in notices:
            key = (notice.bid_ntce_no, notice.bid_ntce_ord)
            data = dict(notice.data)
            data["prtcptPsblRgnNms"] = ", ".join(
                rgn_map.get(notice.bid_ntce_no, [])
            )
            data["permsnIndstrytyListNms"] = ", ".join(
                lic_map.get(notice.bid_ntce_no, [])
            )
            data["indstrytyMfrcFldListNms"] = ", ".join(
                mfrc_map.get(notice.bid_ntce_no, [])
            )
            incntv_names = sorted(set(incntv_map.get(key, [])))
            jnt_names = sorted(set(jnt_map.get(key, [])))
            data["incntvRgnNms"] = ", ".join(incntv_names)
            data["jntcontrctDutyRgnNms"] = ", ".join(jnt_names)
            data["rgnDutyJntcontrctRt"] = (
                jnt_rate.get(key) or data.get("rgnDutyJntcontrctRt")
            )
            data["subsiCnsttys"] = [
                SubsiCnsttyInfo(nm=nm, evlRt=rt)
                for _, nm, rt in sorted(
                    subsi_map.get(key, []), key=lambda t: (t[0], t[1])
                )
            ]
            if location_name:
                data["isIncntvRgnMatch"] = any(
                    location_matches(n, location_name) for n in incntv_names
                )
                data["isJntcontrctDutyRgnMatch"] = any(
                    location_matches(n, location_name) for n in jnt_names
                )
            else:
                data["isIncntvRgnMatch"] = None
                data["isJntcontrctDutyRgnMatch"] = None
            items.append(BidItem(**data))
        return items

    async def save_bid_notices(
        self, db: AsyncSession, items: List[BidItem]
    ) -> int:
        """입찰공고 데이터를 DB에 저장합니다 (upsert)."""
        saved = 0
        for item in items:
            stmt = (
                insert(BidNotice)
                .values(
                    bid_ntce_no=item.bidNtceNo,
                    bid_ntce_ord=item.bidNtceOrd,
                    rgst_dt=normalize_date_str(item.rgstDt),
                    openg_dt=normalize_date_str(item.opengDt),
                    bid_close_dt=normalize_date_str(item.bidClseDt),
                    presmpt_prce=parse_price(item.presmptPrce),
                    main_cnsty_nm=item.mainCnsttyNm,
                    data=item.model_dump(),
                )
                .on_conflict_do_update(
                    index_elements=["bid_ntce_no", "bid_ntce_ord"],
                    set_={
                        "data": item.model_dump(),
                        "rgst_dt": normalize_date_str(item.rgstDt),
                        "openg_dt": normalize_date_str(item.opengDt),
                        "bid_close_dt": normalize_date_str(item.bidClseDt),
                        "presmpt_prce": parse_price(item.presmptPrce),
                        "main_cnsty_nm": item.mainCnsttyNm,
                        "fetched_at": func.now(),
                    },
                )
            )
            await db.execute(stmt)
            saved += 1
        if saved:
            try:
                from app.services.bookmark_service import refresh_dashboard_for_notices

                async with db.begin_nested():
                    await refresh_dashboard_for_notices(
                        db,
                        ((item.bidNtceNo, item.bidNtceOrd) for item in items),
                    )
            except Exception:
                logger.warning(
                    "bookmark_dashboard_refresh_after_bid_notice_save_failed",
                    exc_info=True,
                )
        await db.commit()
        logger.info(f"Saved {saved} bid notices to DB")
        return saved

    async def save_prtcpt_psbl_rgns(
        self, db: AsyncSession, regions: List[PrtcptPsblRgnItem]
    ) -> int:
        """참가가능지역 데이터를 DB에 저장합니다 (upsert)."""
        saved = 0
        for rgn in regions:
            if not rgn.bidNtceNo or rgn.lmtSno is None:
                continue
            stmt = (
                insert(BidPrtcptPsblRgn)
                .values(
                    bid_ntce_no=rgn.bidNtceNo,
                    bid_ntce_ord=rgn.bidNtceOrd or "000",
                    lmt_sno=rgn.lmtSno,
                    prtcpt_psbl_rgn_nm=rgn.prtcptPsblRgnNm,
                    rgst_dt=rgn.rgstDt,
                    bsns_div_nm=rgn.bsnsDivNm,
                )
                .on_conflict_do_nothing()
            )
            await db.execute(stmt)
            saved += 1
        await db.commit()
        logger.info(f"Saved {saved} participation eligible regions to DB")
        return saved

    async def save_license_limits(
        self, db: AsyncSession, items: List[LicenseLimitItem]
    ) -> int:
        """면허제한 데이터를 DB에 저장합니다 (upsert)."""
        saved = 0
        for item in items:
            if not item.bidNtceNo or item.lmtSno is None:
                continue
            stmt = (
                insert(BidLicenseLimit)
                .values(
                    bid_ntce_no=item.bidNtceNo,
                    bid_ntce_ord=item.bidNtceOrd or "000",
                    lmt_grp_no=item.lmtGrpNo or "0",
                    lmt_sno=item.lmtSno or "0",
                    lcns_lmt_nm=item.lcnsLmtNm,
                    permsn_indstryty_list=item.permsnIndstrytyList,
                    bsns_div_nm=item.bsnsDivNm,
                    rgst_dt=item.rgstDt,
                    indstryty_mfrc_fld_list=item.indstrytyMfrcFldList,
                )
                .on_conflict_do_nothing()
            )
            await db.execute(stmt)
            saved += 1
        await db.commit()
        logger.info(f"Saved {saved} license limits to DB")
        return saved

    async def save_incntv_rgns(
        self, db: AsyncSession, items: List[IncntvRgnItem]
    ) -> int:
        """가산지역 데이터를 DB에 저장합니다 (upsert)."""
        saved = 0
        for idx, item in enumerate(items, start=1):
            if not item.bidNtceNo:
                continue
            values = dict(
                bid_ntce_no=item.bidNtceNo,
                bid_ntce_ord=item.bidNtceOrd or DEFAULT_BID_ORD,
                sno=_parse_sno(item.sno, idx),
                incntv_rgn_nm=item.incntvRgnNm,
                ntce_ntice_dt=item.ntceNticeDt,
            )
            await db.execute(self._upsert(BidIncntvRgn, values))
            saved += 1
        await db.commit()
        logger.info(f"Saved {saved} incentive regions to DB")
        return saved

    async def save_jntcontrct_duty_rgns(
        self, db: AsyncSession, items: List[JntcontrctDutyRgnItem]
    ) -> int:
        """공동도급의무지역 데이터를 DB에 저장합니다 (upsert)."""
        saved = 0
        for idx, item in enumerate(items, start=1):
            if not item.bidNtceNo:
                continue
            values = dict(
                bid_ntce_no=item.bidNtceNo,
                bid_ntce_ord=item.bidNtceOrd or DEFAULT_BID_ORD,
                sno=_parse_sno(item.sno, idx),
                jntcontrct_duty_rgn_nm=item.jntcontrctDutyRgnNm,
                rgn_duty_jntcontrct_rt=item.rgnDutyJntcontrctRt,
                ntce_ntice_dt=item.ntceNticeDt,
            )
            await db.execute(self._upsert(BidJntcontrctDutyRgn, values))
            saved += 1
        await db.commit()
        logger.info(f"Saved {saved} joint-contract duty regions to DB")
        return saved

    async def save_subsi_cnsttys(
        self, db: AsyncSession, items: List[SubsiCnsttyItem]
    ) -> int:
        """부공종 데이터를 DB에 저장합니다 (upsert)."""
        saved = 0
        for idx, item in enumerate(items, start=1):
            if not item.bidNtceNo:
                continue
            values = dict(
                bid_ntce_no=item.bidNtceNo,
                bid_ntce_ord=item.bidNtceOrd or DEFAULT_BID_ORD,
                sno=_parse_sno(item.sno, idx),
                subsi_cnstty_cd=item.subsiCnsttyCd,
                subsi_cnstty_nm=item.subsiCnsttyNm,
                subsi_cnstty_indstryty_evl_rt=item.subsiCnsttyIndstrytyEvlRt,
                ntce_ntice_dt=item.ntceNticeDt,
            )
            await db.execute(self._upsert(BidSubsiCnstty, values))
            saved += 1
        await db.commit()
        logger.info(f"Saved {saved} subsidiary constructions to DB")
        return saved

    @staticmethod
    def _upsert(model, values: dict):
        """PK(bid_ntce_no, bid_ntce_ord, sno) 기준 upsert 문."""
        update = {
            k: v
            for k, v in values.items()
            if k not in ("bid_ntce_no", "bid_ntce_ord", "sno")
        }
        update["fetched_at"] = func.now()
        return (
            insert(model)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["bid_ntce_no", "bid_ntce_ord", "sno"],
                set_=update,
            )
        )

    async def get_cached_attachments(
        self, db: AsyncSession, bid_ntce_no: str, bid_ntce_ord: str
    ) -> Optional[list]:
        """첨부파일 캐시 조회. TTL 내면 목록(빈 목록 포함), 없거나 만료면 None."""
        result = await db.execute(
            select(BidAttachmentCache).where(
                BidAttachmentCache.bid_ntce_no == bid_ntce_no,
                BidAttachmentCache.bid_ntce_ord == bid_ntce_ord,
            )
        )
        row = result.scalar_one_or_none()
        if row is None or row.data is None or row.fetched_at is None:
            return None
        kind = getattr(row, "kind", None) or ATTACHMENT_KIND_API
        if kind == ATTACHMENT_KIND_FAILED:
            ttl = ATTACHMENT_FAILED_CACHE_TTL
        elif kind == ATTACHMENT_KIND_LEGACY or not row.data:
            ttl = ATTACHMENT_EMPTY_CACHE_TTL
        else:
            ttl = ATTACHMENT_CACHE_TTL
        fetched_at = row.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - fetched_at > ttl:
            return None
        return row.data

    async def save_attachments_cache(
        self,
        db: AsyncSession,
        bid_ntce_no: str,
        bid_ntce_ord: str,
        data: list,
        kind: str = ATTACHMENT_KIND_API,
    ) -> None:
        """첨부파일 목록 캐시를 저장합니다 (upsert). kind 로 TTL 이 결정된다."""
        stmt = (
            insert(BidAttachmentCache)
            .values(
                bid_ntce_no=bid_ntce_no,
                bid_ntce_ord=bid_ntce_ord,
                data=data,
                kind=kind,
            )
            .on_conflict_do_update(
                index_elements=["bid_ntce_no", "bid_ntce_ord"],
                set_={"data": data, "kind": kind, "fetched_at": func.now()},
            )
        )
        await db.execute(stmt)
        await db.commit()

    async def save_basis_amount(
        self,
        db: AsyncSession,
        bid_ntce_no: str,
        bid_type: str,
        data: dict,
        bid_ntce_ord: str = "000",
    ) -> None:
        """기초금액 정보를 DB에 저장합니다."""
        stmt = (
            insert(BidBasisAmount)
            .values(
                bid_ntce_no=bid_ntce_no,
                bid_ntce_ord=bid_ntce_ord,
                bid_type=bid_type,
                data=data,
            )
            .on_conflict_do_update(
                index_elements=["bid_ntce_no", "bid_ntce_ord", "bid_type"],
                set_={"data": data, "fetched_at": func.now()},
            )
        )
        await db.execute(stmt)
        await db.commit()

    async def get_basis_amount_from_db(
        self,
        db: AsyncSession,
        bid_ntce_no: str,
        bid_type: str,
    ) -> Optional[BidAValueItem]:
        """DB에서 기초금액 정보를 조회합니다."""
        result = await db.execute(
            select(BidBasisAmount).where(
                BidBasisAmount.bid_ntce_no == bid_ntce_no,
                BidBasisAmount.bid_type == bid_type,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            return BidAValueItem(**row.data)
        return None

    async def get_basis_amount_row(
        self,
        db: AsyncSession,
        bid_ntce_no: str,
        bid_type: str,
    ) -> Optional[BidBasisAmount]:
        """DB에서 기초금액 row를 조회합니다 (fetched_at 포함)."""
        result = await db.execute(
            select(BidBasisAmount).where(
                BidBasisAmount.bid_ntce_no == bid_ntce_no,
                BidBasisAmount.bid_type == bid_type,
            )
        )
        return result.scalar_one_or_none()

    async def touch_basis_amount_fetched_at(
        self,
        db: AsyncSession,
        bid_ntce_no: str,
        bid_type: str,
    ) -> None:
        """기초금액 row의 fetched_at만 현재 시각으로 갱신합니다."""
        from sqlalchemy import update

        await db.execute(
            update(BidBasisAmount)
            .where(
                BidBasisAmount.bid_ntce_no == bid_ntce_no,
                BidBasisAmount.bid_type == bid_type,
            )
            .values(fetched_at=func.now())
        )
        await db.commit()

    async def list_pending_reserve_price_targets(
        self,
        db: AsyncSession,
        limit: int = 10,
    ) -> List[tuple[str, str, str, str]]:
        """예정가격(plnprc) 미수집 + 개찰 완료 + 복수예가 공고 N건을 반환합니다.

        Returns: [(bid_ntce_no, bid_ntce_ord, bid_type, openg_dt), ...]
        bid_type 은 BidBasisAmount 에 저장된 값을 사용 (없으면 'cnstwk' default).
        복수예가가 아닌 공고는 plnprc 가 공개되지 않으므로 제외.
        """
        now_yyyymmddhhmm = datetime.now().strftime("%Y%m%d%H%M")
        result = await db.execute(
            select(
                BidNotice.bid_ntce_no,
                BidNotice.bid_ntce_ord,
                func.coalesce(BidBasisAmount.bid_type, "cnstwk"),
                BidNotice.openg_dt,
            )
            .outerjoin(
                BidBasisAmount,
                and_(
                    BidBasisAmount.bid_ntce_no == BidNotice.bid_ntce_no,
                    BidBasisAmount.bid_ntce_ord == BidNotice.bid_ntce_ord,
                ),
            )
            .where(
                BidNotice.openg_dt.isnot(None),
                BidNotice.openg_dt != "",
                BidNotice.openg_dt < now_yyyymmddhhmm,
                BidNotice.data["prearngPrceDcsnMthdNm"].astext.like("%복수예가%"),
                ~exists().where(
                    and_(
                        BidReservePrice.bid_ntce_no == BidNotice.bid_ntce_no,
                        BidReservePrice.bid_ntce_ord == BidNotice.bid_ntce_ord,
                    )
                ),
            )
            .order_by(BidNotice.openg_dt.desc())
            .limit(limit)
        )
        return [(r[0], r[1], r[2], r[3]) for r in result.all()]

    async def save_reserve_price(
        self,
        db: AsyncSession,
        bid_ntce_no: str,
        bid_ntce_ord: str,
        bid_type: str,
        item: Optional[dict],
    ) -> bool:
        """예정가격 항목을 저장합니다.

        item=None 이면 저장하지 않고 False 반환 (다음 사이클 재시도 가능).
        잘못된 bid_type 으로 인한 빈 응답이 영구 누락되지 않도록 함.
        """
        if item is None:
            return False
        bssamt = parse_price(item.get("bssamt"))
        plnprc = parse_price(item.get("plnprc"))
        bsis_plnprc = parse_price(item.get("bsisPlnprc"))
        rl_openg_dt = item.get("rlOpengDt") or None

        stmt = (
            insert(BidReservePrice)
            .values(
                bid_ntce_no=bid_ntce_no,
                bid_ntce_ord=bid_ntce_ord or "000",
                bid_type=bid_type,
                bssamt=bssamt if bssamt else None,
                plnprc=plnprc if plnprc else None,
                bsis_plnprc=bsis_plnprc if bsis_plnprc else None,
                rl_openg_dt=rl_openg_dt,
                data=item,
            )
            .on_conflict_do_update(
                index_elements=["bid_ntce_no", "bid_ntce_ord", "bid_type"],
                set_={
                    "bssamt": bssamt if bssamt else None,
                    "plnprc": plnprc if plnprc else None,
                    "bsis_plnprc": bsis_plnprc if bsis_plnprc else None,
                    "rl_openg_dt": rl_openg_dt,
                    "data": item,
                    "fetched_at": func.now(),
                },
            )
        )
        await db.execute(stmt)
        await db.commit()
        return True

    async def has_synced_data(
        self, db: AsyncSession, start_date: str, end_date: str
    ) -> bool:
        """날짜 범위가 동기화되었는지 확인합니다.

        과거 날짜는 일별 윈도우(YYYYMMDD0000~YYYYMMDD2359) 존재로 판단합니다.
        오늘(KST)은 일별 마커로는 신뢰할 수 없습니다 — 새 공고가 계속 등록되므로
        시간별 freshness 검사가 필요합니다. 오늘이 포함된 범위는 항상 False를
        반환하여, 호출자가 시간별 sync 경로로 처리하도록 강제합니다.
        """
        today_str = datetime.now(KST).strftime("%Y%m%d")
        start_d = start_date[:8]
        end_d = end_date[:8]

        try:
            start_dt = datetime.strptime(start_d, "%Y%m%d")
            end_dt = datetime.strptime(end_d, "%Y%m%d")
        except ValueError:
            return False

        # 오늘 또는 미래 포함 시 시간별 freshness 필요 — 호출자에 위임
        if end_d >= today_str:
            return False

        expected_days = (end_dt - start_dt).days + 1

        result = await db.execute(
            select(func.count()).select_from(DataSyncLog).where(
                DataSyncLog.sync_timestamp >= start_d + "0000",
                DataSyncLog.sync_timestamp <= end_d + "0000",
                DataSyncLog.window_end.like("%2359"),
            )
        )
        synced_days = result.scalar() or 0
        return synced_days >= expected_days

    async def get_missing_synced_days(
        self, db: AsyncSession, start_date: str, end_date: str
    ) -> List[str]:
        """날짜 범위에서 일별 윈도우(YYYYMMDD2359)가 없는 일자 목록을 반환합니다.

        오늘(KST)은 일별 마커가 있어도 항상 missing 으로 포함됩니다 —
        호출자는 오늘에 한해 시간별 윈도우로 처리해야 합니다.
        미래 날짜는 missing 에 포함하지 않습니다 (sync 대상 아님).
        """
        today_str = datetime.now(KST).strftime("%Y%m%d")
        start_d = start_date[:8]
        end_d = end_date[:8]

        try:
            start_dt = datetime.strptime(start_d, "%Y%m%d")
            end_dt = datetime.strptime(end_d, "%Y%m%d")
        except ValueError:
            return []

        result = await db.execute(
            select(DataSyncLog.sync_timestamp).where(
                DataSyncLog.sync_timestamp >= start_d + "0000",
                DataSyncLog.sync_timestamp <= end_d + "0000",
                DataSyncLog.window_end.like("%2359"),
            )
        )
        synced_set = {row[0][:8] for row in result.all()}

        missing: List[str] = []
        current = start_dt
        while current <= end_dt:
            d = current.strftime("%Y%m%d")
            if d > today_str:
                break
            if d == today_str or d not in synced_set:
                missing.append(d)
            current += timedelta(days=1)
        return missing

    async def is_today_hour_fresh(
        self, db: AsyncSession, max_age_seconds: int = 3600
    ) -> bool:
        """현재 KST 시각의 시간별 윈도우가 max_age_seconds 이내 동기화됐는지 확인."""
        now_kst = datetime.now(KST)
        ts = now_kst.strftime("%Y%m%d%H") + "00"
        end = now_kst.strftime("%Y%m%d%H") + "59"
        entry = await self.get_sync_entry(db, ts, end)
        if not entry or not entry.synced_at:
            return False
        synced = entry.synced_at
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - synced).total_seconds()
        return age < max_age_seconds

    async def get_sync_entry(
        self, db: AsyncSession, sync_timestamp: str, window_end: str
    ) -> DataSyncLog | None:
        """특정 윈도우의 sync 엔트리를 조회합니다.

        window_end 가 필수인 이유: 자정 시간별 윈도우(d0000~d0059)와
        일별 백필 윈도우(d0000~d2359)는 sync_timestamp 가 같다. 시작 시각만으로
        조회하면 시간별 기록을 일별 완료로 오인해 백필을 영구히 건너뛴다.
        """
        result = await db.execute(
            select(DataSyncLog).where(
                DataSyncLog.sync_timestamp == sync_timestamp,
                DataSyncLog.window_end == window_end,
            )
        )
        return result.scalar_one_or_none()

    async def get_daily_sync_entry(
        self, db: AsyncSession, date_str: str
    ) -> DataSyncLog | None:
        """해당 일자의 '일별' 윈도우(YYYYMMDD0000~YYYYMMDD2359) 엔트리를 조회합니다."""
        return await self.get_sync_entry(
            db, f"{date_str}0000", f"{date_str}2359"
        )

    async def mark_window_synced(
        self,
        db: AsyncSession,
        sync_timestamp: str,
        window_end: str,
        total_notices: int,
        total_regions: int,
        total_license_limits: int = 0,
        *,
        total_incntv_rgns: int = 0,
        total_jntcontrct_duty_rgns: int = 0,
        total_subsi_cnsttys: int = 0,
        sub_datasets_synced: bool = False,
    ) -> None:
        """시간 윈도우를 동기화 완료로 마킹합니다.

        sub_datasets_synced: 가산지역/공동도급의무지역/부공종 3종 수집 성공 여부.
        (공고/지역/면허 성공만으로 윈도우는 마킹되고, 3종은 별도 재시도된다.)
        """
        stmt = (
            insert(DataSyncLog)
            .values(
                sync_timestamp=sync_timestamp,
                window_end=window_end,
                total_notices=total_notices,
                total_regions=total_regions,
                total_license_limits=total_license_limits,
                total_incntv_rgns=total_incntv_rgns,
                total_jntcontrct_duty_rgns=total_jntcontrct_duty_rgns,
                total_subsi_cnsttys=total_subsi_cnsttys,
                sub_datasets_synced=sub_datasets_synced,
            )
            .on_conflict_do_update(
                index_elements=["sync_timestamp", "window_end"],
                set_={
                    "synced_at": func.now(),
                    "total_notices": total_notices,
                    "total_regions": total_regions,
                    "total_license_limits": total_license_limits,
                    "total_incntv_rgns": total_incntv_rgns,
                    "total_jntcontrct_duty_rgns": total_jntcontrct_duty_rgns,
                    "total_subsi_cnsttys": total_subsi_cnsttys,
                    "sub_datasets_synced": sub_datasets_synced,
                },
            )
        )
        await db.execute(stmt)
        await db.commit()

    async def list_windows_pending_sub_datasets(
        self, db: AsyncSession, limit: int, days: int = 30
    ) -> List[tuple]:
        """부속 데이터셋 3종이 아직 수집되지 않은 '일별' 윈도우 (최신순).

        일별 윈도우 = 시작이 0000 이고 끝이 2359 (23시 시간별 윈도우는 시작이 2300).
        반환: [(sync_timestamp, window_end), ...]
        """
        cutoff = (datetime.now(KST) - timedelta(days=days)).strftime("%Y%m%d") + "0000"
        result = await db.execute(
            select(DataSyncLog.sync_timestamp, DataSyncLog.window_end)
            .where(
                DataSyncLog.sub_datasets_synced.is_(False),
                DataSyncLog.sync_timestamp.like("%0000"),
                DataSyncLog.window_end.like("%2359"),
                DataSyncLog.sync_timestamp >= cutoff,
            )
            .order_by(DataSyncLog.sync_timestamp.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def mark_sub_datasets_synced(
        self,
        db: AsyncSession,
        sync_timestamp: str,
        window_end: str,
        total_incntv_rgns: int,
        total_jntcontrct_duty_rgns: int,
        total_subsi_cnsttys: int,
    ) -> None:
        """부속 데이터셋 재수집 성공 후 플래그와 건수를 갱신합니다."""
        await db.execute(
            update(DataSyncLog)
            .where(
                DataSyncLog.sync_timestamp == sync_timestamp,
                DataSyncLog.window_end == window_end,
            )
            .values(
                sub_datasets_synced=True,
                total_incntv_rgns=total_incntv_rgns,
                total_jntcontrct_duty_rgns=total_jntcontrct_duty_rgns,
                total_subsi_cnsttys=total_subsi_cnsttys,
            )
        )
        await db.commit()

    async def get_user_location(
        self, db: AsyncSession, user_id
    ) -> Optional[UserLocation]:
        """사용자 소재지를 조회합니다."""
        result = await db.execute(
            select(UserLocation).where(UserLocation.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def set_user_location(
        self, db: AsyncSession, user_id, location_name: str
    ) -> UserLocation:
        """사용자 소재지를 등록/수정합니다."""
        existing = await self.get_user_location(db, user_id)
        if existing:
            existing.location_name = location_name
            await db.commit()
            await db.refresh(existing)
            return existing

        new_location = UserLocation(
            user_id=user_id,
            location_name=location_name,
        )
        db.add(new_location)
        await db.commit()
        await db.refresh(new_location)
        return new_location

    async def delete_user_location(self, db: AsyncSession, user_id) -> bool:
        """사용자 소재지를 삭제합니다."""
        result = await db.execute(
            select(UserLocation).where(UserLocation.user_id == user_id)
        )
        location = result.scalar_one_or_none()
        if location:
            await db.delete(location)
            await db.commit()
            return True
        return False


bid_data_service = BidDataService()
