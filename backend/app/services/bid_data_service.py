import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

KST = timezone(timedelta(hours=9))

from sqlalchemy import BigInteger, and_, cast, exists, func, nullslast, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.bid import (
    BidBasisAmount,
    BidLicenseLimit,
    BidNotice,
    BidPrtcptPsblRgn,
    BidReservePrice,
    DataSyncLog,
    UserLocation,
)
from app.schemas.bid import (
    BidApiResponse,
    BidAValueItem,
    BidItem,
    BidSearchParams,
    LicenseLimitItem,
    PrtcptPsblRgnItem,
)

logger = logging.getLogger(__name__)


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


class BidDataService:
    """DB 기반 입찰 데이터 서비스"""

    async def search_from_db(
        self,
        db: AsyncSession,
        params: BidSearchParams,
        user_id=None,
    ) -> BidApiResponse:
        """DB에서 입찰공고를 검색합니다."""
        query = select(BidNotice)

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

        if params.useLocationFilter and user_id:
            location = await self.get_user_location(db, user_id)
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

        # 업종명 필터 (면허제한명 + 허용업종목록 기반, EXISTS)
        # 참가가능지역 필터와 동일하게 "면허 정보가 아예 없는 공고"는 배제하지
        # 않는다. 면허제한 수집이 실패한 공고까지 검색결과에서 통째로 사라지면
        # 사용자는 누락 사실 자체를 알 수 없다. 업종제한이 없는 공고
        # (indstrytyLmtYn='N') 도 같은 이유로 살려둔다.
        if params.indstrytyNm:
            LicAlias = aliased(BidLicenseLimit)
            industries = [i.strip() for i in params.indstrytyNm.split(",")]
            industry_conditions = []
            for ind in industries:
                industry_conditions.append(
                    LicAlias.lcns_lmt_nm.ilike(f"%{ind}%")
                )
                industry_conditions.append(
                    LicAlias.permsn_indstryty_list.ilike(f"%{ind}%")
                )
            no_license_info = ~exists(
                select(LicAlias.bid_ntce_no).where(
                    LicAlias.bid_ntce_no == BidNotice.bid_ntce_no,
                    LicAlias.bid_ntce_ord == BidNotice.bid_ntce_ord,
                )
            )
            has_matching_industry = exists(
                select(LicAlias.bid_ntce_no).where(
                    LicAlias.bid_ntce_no == BidNotice.bid_ntce_no,
                    LicAlias.bid_ntce_ord == BidNotice.bid_ntce_ord,
                    or_(*industry_conditions),
                )
            )
            query = query.where(or_(no_license_info, has_matching_industry))

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
        if order_col is not None:
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

        # 참가가능지역 + 허용업종목록을 각 공고에 추가
        items = []
        if notices:
            bid_nos = list({n.bid_ntce_no for n in notices})

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

            for notice in notices:
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
                items.append(BidItem(**data))

        return BidApiResponse(
            items=items,
            totalCount=total_count,
            numOfRows=params.numOfRows,
            pageNo=params.pageNo,
        )

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
    ) -> None:
        """시간 윈도우를 동기화 완료로 마킹합니다."""
        stmt = (
            insert(DataSyncLog)
            .values(
                sync_timestamp=sync_timestamp,
                window_end=window_end,
                total_notices=total_notices,
                total_regions=total_regions,
                total_license_limits=total_license_limits,
            )
            .on_conflict_do_update(
                index_elements=["sync_timestamp", "window_end"],
                set_={
                    "synced_at": func.now(),
                    "total_notices": total_notices,
                    "total_regions": total_regions,
                    "total_license_limits": total_license_limits,
                },
            )
        )
        await db.execute(stmt)
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
