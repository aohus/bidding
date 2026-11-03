"""GET /bids/{bidNtceNo}/attachments 테스트.

고정하는 동작:
  1. 저장된 공고만 조회 (없으면 404, 업스트림 호출 없음).
  2. 캐시 → API(공고+전자발주) → 캐시 저장. kind: api / legacy / failed.
  3. API 오류/빈 결과는 저장된 공고의 레거시 URL 로 폴백 (오류는 failed 로 네거티브 캐시).
  4. 동시 miss 는 업스트림 1회 (single-flight), 사용자별 분당 제한(429).
  5. bidType/공고번호/차수 입력 검증, http(s) 이외 URL 거부.
  6. /{bidNtceNo}/detail 은 enrichment 를 거친다.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import bids
from app.api.auth import get_current_user
from app.db.database import get_db
from app.schemas.bid import BidAttachmentItem, BidEorderAttachmentItem
from app.services.narajangter import NaraJangterApiError, RateLimitError


@pytest.fixture(autouse=True)
def _reset_limiter():
    bids.attachments_rate_limiter.reset()
    yield
    bids.attachments_rate_limiter.reset()


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def app(db):
    application = FastAPI()
    application.include_router(bids.router)
    application.dependency_overrides[get_current_user] = lambda: MagicMock()
    application.dependency_overrides[get_db] = lambda: db
    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def ntce_item(**kw):
    base = dict(
        bidNtceNo="R26", bidNtceOrd="000", atchSno="1", atchDocDivNm="공고서",
        atchFileNm="공고문.pdf", atchFileUrl="https://www.g2b.go.kr/a.pdf",
    )
    base.update(kw)
    return BidAttachmentItem(**base)


def eorder_item(**kw):
    base = dict(
        bidNtceNo="R26", bidNtceOrd="000", atchSno="2", eorderDocDivNm="제안요청서",
        eorderAtchFileNm="제안요청서.hwp", eorderAtchFileUrl="http://www.g2b.go.kr/b.hwp",
    )
    base.update(kw)
    return BidEorderAttachmentItem(**base)


def legacy_data(**kw):
    return {
        "ntceSpecDocUrl1": "https://old/1.pdf", "ntceSpecFileNm1": "old1.pdf",
        "sptDscrptDocUrl1": "https://old/s1.pdf", "sptDscrptFileNm1": "s1.pdf",
        "stdNtceDocUrl": "https://old/std.pdf", **kw,
    }


def setup(
    *, cache=None, ntce=None, eorder=None, ntce_exc=None, notice_data=None,
    notice_missing=False, db=None,
):
    """서비스 의존성 patch 묶음. cache=None → miss. 공고는 기본적으로 존재."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = (
        None
        if notice_missing
        else SimpleNamespace(data={} if notice_data is None else notice_data)
    )
    db.execute = AsyncMock(return_value=result)
    svc = MagicMock()
    svc.get_attachments_by_bid = AsyncMock(
        side_effect=ntce_exc, return_value=ntce or []
    )
    svc.get_eorder_attachments_by_bid = AsyncMock(return_value=eorder or [])
    data_svc = MagicMock()
    data_svc.get_cached_attachments = AsyncMock(return_value=cache)
    data_svc.save_attachments_cache = AsyncMock()
    return svc, data_svc


def patched(svc, data_svc):
    return (
        patch("app.api.bids.narajangter_service", svc),
        patch("app.api.bids.bid_data_service", data_svc),
    )


async def get(client, svc, data_svc, url="/bids/R26/attachments?bidNtceOrd=000&bidType=cnstwk"):
    p1, p2 = patched(svc, data_svc)
    with p1, p2:
        return await client.get(url)


class TestAttachmentsFlow:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self, client, db):
        cached = [{"source": "ntce", "docDivNm": None, "fileNm": "c.pdf",
                   "fileUrl": "https://x/c.pdf", "sno": 1}]
        svc, data_svc = setup(cache=cached, db=db)
        r = await get(client, svc, data_svc)

        assert r.status_code == 200
        assert r.json()["items"][0]["fileNm"] == "c.pdf"
        svc.get_attachments_by_bid.assert_not_awaited()
        data_svc.save_attachments_cache.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_api_results_are_mapped_and_cached(self, client, db):
        svc, data_svc = setup(ntce=[ntce_item()], eorder=[eorder_item()], db=db)
        r = await get(client, svc, data_svc)

        body = r.json()
        assert body["bidNtceNo"] == "R26" and body["bidNtceOrd"] == "000"
        assert [i["source"] for i in body["items"]] == ["ntce", "eorder"]
        assert body["items"][0] == {
            "source": "ntce", "docDivNm": "공고서", "fileNm": "공고문.pdf",
            "fileUrl": "https://www.g2b.go.kr/a.pdf", "sno": 1,
        }
        assert body["items"][1]["sno"] == 2
        svc.get_attachments_by_bid.assert_awaited_once_with("R26", "000", "cnstwk")
        svc.get_eorder_attachments_by_bid.assert_awaited_once_with("R26", "000")
        data_svc.save_attachments_cache.assert_awaited_once()
        saved = data_svc.save_attachments_cache.await_args.args
        assert saved[1:3] == ("R26", "000")
        assert len(saved[3]) == 2
        assert data_svc.save_attachments_cache.await_args.kwargs["kind"] == "api"

    @pytest.mark.asyncio
    async def test_servc_passes_bid_type(self, client, db):
        svc, data_svc = setup(ntce=[ntce_item()], db=db)
        await get(client, svc, data_svc, "/bids/R26/attachments?bidType=servc")
        svc.get_attachments_by_bid.assert_awaited_once_with("R26", "000", "servc")

    @pytest.mark.asyncio
    async def test_non_numeric_sno_becomes_null(self, client, db):
        svc, data_svc = setup(ntce=[ntce_item(atchSno="x")], db=db)
        r = await get(client, svc, data_svc)
        assert r.json()["items"][0]["sno"] is None

    @pytest.mark.asyncio
    async def test_unsafe_and_missing_urls_are_dropped(self, client, db):
        svc, data_svc = setup(
            ntce=[
                ntce_item(atchFileUrl="javascript:alert(1)"),
                ntce_item(atchFileUrl="file:///etc/passwd"),
                ntce_item(atchFileUrl=None),
                ntce_item(atchFileUrl="https://ok/z.pdf", atchFileNm="z.pdf"),
            ],
            notice_data={}, db=db,
        )
        r = await get(client, svc, data_svc)
        urls = [i["fileUrl"] for i in r.json()["items"]]
        assert urls == ["https://ok/z.pdf"]

    @pytest.mark.asyncio
    async def test_empty_api_falls_back_to_legacy_and_caches(self, client, db):
        svc, data_svc = setup(notice_data=legacy_data(), db=db)
        r = await get(client, svc, data_svc)

        items = r.json()["items"]
        assert {i["source"] for i in items} == {"legacy"}
        assert [i["fileUrl"] for i in items] == [
            "https://old/1.pdf", "https://old/s1.pdf", "https://old/std.pdf",
        ]
        data_svc.save_attachments_cache.assert_awaited_once()
        # API 정상 + 빈 결과 -> 1시간 TTL 의 legacy 종류 (24시간 아님)
        assert data_svc.save_attachments_cache.await_args.kwargs["kind"] == "legacy"

    @pytest.mark.asyncio
    async def test_empty_api_and_no_legacy_returns_empty_and_caches(self, client, db):
        svc, data_svc = setup(notice_data={}, db=db)
        r = await get(client, svc, data_svc)
        assert r.json()["items"] == []
        data_svc.save_attachments_cache.assert_awaited_once()
        assert data_svc.save_attachments_cache.await_args.args[3] == []
        assert data_svc.save_attachments_cache.await_args.kwargs["kind"] == "api"

    @pytest.mark.asyncio
    async def test_unknown_notice_is_404_without_any_upstream_call(self, client, db):
        svc, data_svc = setup(notice_missing=True, db=db)
        r = await get(client, svc, data_svc)
        assert r.status_code == 404
        svc.get_attachments_by_bid.assert_not_awaited()
        svc.get_eorder_attachments_by_bid.assert_not_awaited()
        data_svc.get_cached_attachments.assert_not_awaited()
        data_svc.save_attachments_cache.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc", [NaraJangterApiError("x"), RateLimitError("y")])
    async def test_api_error_falls_back_to_legacy_with_negative_cache(self, client, db, exc):
        svc, data_svc = setup(ntce_exc=exc, notice_data=legacy_data(), db=db)
        r = await get(client, svc, data_svc)

        assert r.status_code == 200
        assert [i["source"] for i in r.json()["items"]] == ["legacy"] * 3
        data_svc.save_attachments_cache.assert_awaited_once()
        assert data_svc.save_attachments_cache.await_args.kwargs["kind"] == "failed"

    @pytest.mark.asyncio
    async def test_api_error_without_legacy_returns_empty_negative_cached(self, client, db):
        svc, data_svc = setup(ntce_exc=NaraJangterApiError("x"), notice_data={}, db=db)
        r = await get(client, svc, data_svc)
        assert r.status_code == 200 and r.json()["items"] == []
        assert data_svc.save_attachments_cache.await_args.kwargs["kind"] == "failed"

    @pytest.mark.asyncio
    async def test_partial_failure_keeps_api_items_but_short_ttl(self, client, db):
        svc, data_svc = setup(ntce=[ntce_item()], db=db)
        svc.get_eorder_attachments_by_bid.side_effect = NaraJangterApiError("x")
        r = await get(client, svc, data_svc)
        assert [i["source"] for i in r.json()["items"]] == ["ntce"]
        assert data_svc.save_attachments_cache.await_args.kwargs["kind"] == "failed"

    @pytest.mark.asyncio
    async def test_unsafe_legacy_urls_are_dropped(self, client, db):
        svc, data_svc = setup(
            notice_data={"ntceSpecDocUrl1": "javascript:x", "ntceSpecFileNm1": "a",
                         "stdNtceDocUrl": "ftp://h/x"},
            db=db,
        )
        r = await get(client, svc, data_svc)
        assert r.json()["items"] == []

    @pytest.mark.asyncio
    async def test_cache_failure_does_not_break_response(self, client, db):
        svc, data_svc = setup(ntce=[ntce_item()], db=db)
        data_svc.save_attachments_cache.side_effect = RuntimeError("db down")
        r = await get(client, svc, data_svc)
        assert r.status_code == 200 and len(r.json()["items"]) == 1


class TestSingleFlight:
    @pytest.mark.asyncio
    async def test_concurrent_misses_make_one_upstream_round_trip(self, client, db):
        import asyncio

        svc, data_svc = setup(ntce=[ntce_item()], db=db)
        store = {}

        async def slow_ntce(*a, **k):
            await asyncio.sleep(0.05)
            return [ntce_item()]

        async def get_cache(_db, no, ord_):
            return store.get((no, ord_))

        async def save_cache(_db, no, ord_, data, kind="api"):
            store[(no, ord_)] = data

        svc.get_attachments_by_bid = AsyncMock(side_effect=slow_ntce)
        data_svc.get_cached_attachments = AsyncMock(side_effect=get_cache)
        data_svc.save_attachments_cache = AsyncMock(side_effect=save_cache)

        p1, p2 = patched(svc, data_svc)
        with p1, p2:
            rs = await asyncio.gather(
                *[client.get("/bids/R26/attachments") for _ in range(6)]
            )

        assert [r.status_code for r in rs] == [200] * 6
        assert all(len(r.json()["items"]) == 1 for r in rs)
        assert svc.get_attachments_by_bid.await_count == 1
        assert svc.get_eorder_attachments_by_bid.await_count == 1

    @pytest.mark.asyncio
    async def test_different_keys_do_not_share_a_lock(self, client, db):
        import asyncio

        svc, data_svc = setup(ntce=[ntce_item()], db=db)
        p1, p2 = patched(svc, data_svc)
        with p1, p2:
            await asyncio.gather(
                client.get("/bids/R26/attachments"),
                client.get("/bids/R27/attachments"),
            )
        assert svc.get_attachments_by_bid.await_count == 2

    def test_lock_registry_does_not_grow(self):
        before = len(bids._attachment_locks)
        for i in range(1000):
            bids._attachment_lock(f"k{i}:000")
        import gc

        gc.collect()
        assert len(bids._attachment_locks) <= before


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_31st_request_in_a_minute_is_429_with_korean_detail(self, app, db):
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id="u1")
        svc, data_svc = setup(cache=[], db=db)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            p1, p2 = patched(svc, data_svc)
            with p1, p2:
                codes = [
                    (await ac.get("/bids/R26/attachments")).status_code
                    for _ in range(bids.ATTACHMENTS_RATE_LIMIT + 1)
                ]
                blocked = await ac.get("/bids/R26/attachments")
        assert codes[:-1] == [200] * bids.ATTACHMENTS_RATE_LIMIT
        assert codes[-1] == 429
        assert blocked.json()["detail"] == bids.ATTACHMENTS_RATE_LIMIT_DETAIL
        assert "너무 많습니다" in blocked.json()["detail"]

    @pytest.mark.asyncio
    async def test_limit_is_per_user(self, app, db):
        current = {"id": "u1"}
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            user_id=current["id"]
        )
        svc, data_svc = setup(cache=[], db=db)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            p1, p2 = patched(svc, data_svc)
            with p1, p2:
                for _ in range(bids.ATTACHMENTS_RATE_LIMIT):
                    await ac.get("/bids/R26/attachments")
                assert (await ac.get("/bids/R26/attachments")).status_code == 429
                current["id"] = "u2"
                assert (await ac.get("/bids/R26/attachments")).status_code == 200

    @pytest.mark.asyncio
    async def test_limited_request_never_reaches_services(self, app, db):
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id="u1")
        svc, data_svc = setup(db=db)
        bids.attachments_rate_limiter.max_requests = 0
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                p1, p2 = patched(svc, data_svc)
                with p1, p2:
                    r = await ac.get("/bids/R26/attachments")
        finally:
            bids.attachments_rate_limiter.max_requests = bids.ATTACHMENTS_RATE_LIMIT
        assert r.status_code == 429
        data_svc.get_cached_attachments.assert_not_awaited()
        svc.get_attachments_by_bid.assert_not_awaited()


class TestAttachmentsValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url",
        [
            "/bids/R26/attachments?bidType=goods",
            "/bids/R26/attachments?bidType=",
            "/bids/R26/attachments?bidNtceOrd=abcd",
            "/bids/R26/attachments?bidNtceOrd=",
            "/bids/R26'%20OR%201=1/attachments",
            "/bids/" + "A" * 60 + "/attachments",
        ],
    )
    async def test_invalid_input_is_422_and_never_hits_services(self, client, db, url):
        svc, data_svc = setup(db=db)
        r = await get(client, svc, data_svc, url)
        assert r.status_code == 422
        svc.get_attachments_by_bid.assert_not_awaited()
        data_svc.get_cached_attachments.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_defaults_apply(self, client, db):
        svc, data_svc = setup(ntce=[ntce_item()], db=db)
        r = await get(client, svc, data_svc, "/bids/R26/attachments")
        assert r.status_code == 200
        svc.get_attachments_by_bid.assert_awaited_once_with("R26", "000", "cnstwk")

    @pytest.mark.asyncio
    async def test_requires_auth(self, app, db):
        app.dependency_overrides.pop(get_current_user)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            r = await ac.get("/bids/R26/attachments")
        assert r.status_code in (401, 403)


class TestDetailEnrichment:
    @pytest.mark.asyncio
    async def test_detail_uses_enrichment_with_user_location(self, client, db):
        notice = SimpleNamespace(
            bid_ntce_no="R26", bid_ntce_ord="000",
            data={"bidNtceNo": "R26", "bidNtceOrd": "000", "bidNtceNm": "n", "ntceInsttNm": "i"},
        )
        res = MagicMock()
        res.scalar_one_or_none.return_value = notice
        db.execute = AsyncMock(return_value=res)
        enriched = bids.BidItem(
            bidNtceNo="R26", bidNtceOrd="000", bidNtceNm="n", ntceInsttNm="i",
            incntvRgnNms="부산광역시", isIncntvRgnMatch=True,
        )
        data_svc = MagicMock()
        data_svc.get_user_location = AsyncMock(
            return_value=SimpleNamespace(location_name="부산광역시")
        )
        data_svc.enrich_notices = AsyncMock(return_value=[enriched])
        with patch("app.api.bids.bid_data_service", data_svc):
            r = await client.get("/bids/R26/detail")

        assert r.status_code == 200
        assert r.json()["incntvRgnNms"] == "부산광역시"
        assert data_svc.enrich_notices.await_args.args[2] == "부산광역시"

    @pytest.mark.asyncio
    async def test_detail_without_location_passes_none(self, client, db):
        notice = SimpleNamespace(
            bid_ntce_no="R26", bid_ntce_ord="000",
            data={"bidNtceNo": "R26", "bidNtceOrd": "000", "bidNtceNm": "n", "ntceInsttNm": "i"},
        )
        res = MagicMock()
        res.scalar_one_or_none.return_value = notice
        db.execute = AsyncMock(return_value=res)
        data_svc = MagicMock()
        data_svc.get_user_location = AsyncMock(return_value=None)
        data_svc.enrich_notices = AsyncMock(
            return_value=[bids.BidItem(bidNtceNo="R26", bidNtceOrd="000", bidNtceNm="n", ntceInsttNm="i")]
        )
        with patch("app.api.bids.bid_data_service", data_svc):
            await client.get("/bids/R26/detail")
        assert data_svc.enrich_notices.await_args.args[2] is None

    @pytest.mark.asyncio
    async def test_detail_404(self, client, db):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=res)
        r = await client.get("/bids/R26/detail")
        assert r.status_code == 404
