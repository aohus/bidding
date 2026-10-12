"""외부기관 조회 API 테스트.

고정하는 핵심 동작:
  1. 라우트가 bids 라우터의 /bids/{bidNtceNo}/... 가변 경로에 가로채지지 않는다.
  2. 알 수 없는 기관 식별자는 400 으로 거절한다 (조용히 빈 결과 금지).
  3. 응답이 external_bid_* 데이터만 담는다 — 나라장터 /bids/search 는 무영향.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import external_bids
from app.api.auth import get_admin_user, get_current_user
from app.db.database import get_db
from app.models.external_bid import ExternalBidNotice, ExternalBidResult


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(external_bids.router)
    application.dependency_overrides[get_current_user] = lambda: MagicMock()
    application.dependency_overrides[get_admin_user] = lambda: MagicMock()
    application.dependency_overrides[get_db] = lambda: MagicMock()
    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def notice_row(**kwargs) -> ExternalBidNotice:
    row = ExternalBidNotice(
        source=kwargs.get("source", "kdhc"),
        notice_no=kwargs.get("notice_no", "305100-26070"),
        notice_ord=kwargs.get("notice_ord", "00"),
        title=kwargs.get("title", "테스트 용역"),
        institution=kwargs.get("institution", "수원사업소 고객지원부"),
        work_div=kwargs.get("work_div", "용역"),
        cntrct_mthd=kwargs.get("cntrct_mthd", None),
        rgst_dt=kwargs.get("rgst_dt", "202610070000"),
        bid_close_dt=kwargs.get("bid_close_dt", None),
        openg_dt=kwargs.get("openg_dt", "202610080000"),
        presmpt_prce=kwargs.get("presmpt_prce", None),
        status=kwargs.get("status", "낙찰"),
        data=kwargs.get("data", {"bidAnnoNo": "305100-26070"}),
    )
    return row


def result_row(**kwargs) -> ExternalBidResult:
    return ExternalBidResult(
        source=kwargs.get("source", "kwater"),
        notice_no=kwargs.get("notice_no", "B1202201899"),
        notice_ord="000",
        seq=kwargs.get("seq", 0),
        title="완도수도지사 분광광도계 구매",
        bidder_nm="(주)동양화학",
        bidder_amt=37086150,
        status_nm="낙찰",
        openg_dt="202205260000",
        data={"tndrPbanno": "B1202201899"},
    )


def patch_search(rows=None, total=0):
    svc = MagicMock()
    svc.search_notices = AsyncMock(return_value=(rows or [], total))
    svc.search_results = AsyncMock(return_value=(rows or [], total))
    return patch("app.api.external_bids.external_bid_service", svc), svc


# ---------------------------------------------------------------------------
# 라우팅
# ---------------------------------------------------------------------------

class TestRouting:
    def test_prefix_is_not_nested_under_bids(self):
        """/bids/external/results 는 /bids/{bidNtceNo}/results 에 가로채진다."""
        assert external_bids.router.prefix == "/external-bids"

    def test_full_app_exposes_external_and_bid_results_separately(self):
        """실제 앱(bids 라우터 포함)에서 경로가 가로채지지 않는지 확인.

        app.routes 는 이 FastAPI 버전에서 라우터를 _IncludedRouter 로 중첩
        보관하므로 리프 경로가 보이지 않는다 — OpenAPI 스키마가 공개 계약이다.
        """
        from app.main import app as real_app

        paths = real_app.openapi()["paths"]
        assert "/external-bids/results" in paths
        # 나라장터 가변 경로가 여전히 살아있어야 한다 (기존 기능 무영향).
        assert "/bids/{bidNtceNo}/results" in paths

    def test_external_paths_do_not_live_under_bids(self):
        from app.main import app as real_app

        external = [
            p for p in real_app.openapi()["paths"] if "external" in p
        ]
        assert external
        for path in external:
            assert not path.startswith("/bids")


# ---------------------------------------------------------------------------
# 기관 목록
# ---------------------------------------------------------------------------

class TestListSources:
    @pytest.mark.asyncio
    async def test_lists_all_six_agencies(self, client):
        response = await client.get("/external-bids/sources")

        assert response.status_code == 200
        sources = {s["source"] for s in response.json()["sources"]}
        assert sources == {"lh", "kwater", "kdhc", "kra", "kogas", "kepco"}

    @pytest.mark.asyncio
    async def test_includes_korean_names(self, client):
        response = await client.get("/external-bids/sources")

        by_id = {s["source"]: s for s in response.json()["sources"]}
        assert by_id["lh"]["name"] == "한국토지주택공사"
        assert by_id["kwater"]["granularity"] == "month"


# ---------------------------------------------------------------------------
# 공고 조회
# ---------------------------------------------------------------------------

class TestSearchNotices:
    @pytest.mark.asyncio
    async def test_returns_mapped_items(self, client):
        ctx, _ = patch_search(rows=[notice_row()], total=1)
        with ctx:
            response = await client.get("/external-bids")

        assert response.status_code == 200
        payload = response.json()
        assert payload["totalCount"] == 1
        item = payload["items"][0]
        assert item["source"] == "kdhc"
        assert item["sourceName"] == "한국지역난방공사"
        assert item["noticeNo"] == "305100-26070"
        assert item["title"] == "테스트 용역"
        assert item["raw"]["bidAnnoNo"] == "305100-26070"

    @pytest.mark.asyncio
    async def test_empty_result_is_200_not_404(self, client):
        ctx, _ = patch_search()
        with ctx:
            response = await client.get("/external-bids")

        assert response.status_code == 200
        assert response.json()["items"] == []

    @pytest.mark.asyncio
    async def test_passes_filters_through(self, client):
        ctx, svc = patch_search()
        with ctx:
            await client.get(
                "/external-bids",
                params={
                    "source": "kdhc,kra",
                    "dateFrom": "202610010000",
                    "dateTo": "202610122359",
                    "keyword": "용역",
                    "pageNo": 2,
                    "numOfRows": 50,
                },
            )

        kwargs = svc.search_notices.await_args.kwargs
        assert kwargs["source"] == "kdhc,kra"
        assert kwargs["date_from"] == "202610010000"
        assert kwargs["date_to"] == "202610122359"
        assert kwargs["keyword"] == "용역"
        assert kwargs["page_no"] == 2
        assert kwargs["num_of_rows"] == 50

    @pytest.mark.asyncio
    async def test_unknown_source_is_rejected(self, client):
        """조용히 빈 결과를 주면 오타를 '데이터 없음'으로 오인한다."""
        ctx, svc = patch_search()
        with ctx:
            response = await client.get(
                "/external-bids", params={"source": "nope"}
            )

        assert response.status_code == 400
        assert "nope" in response.json()["detail"]
        svc.search_notices.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partially_unknown_source_is_rejected(self, client):
        ctx, _ = patch_search()
        with ctx:
            response = await client.get(
                "/external-bids", params={"source": "kdhc,bogus"}
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rows_cap_is_enforced(self, client):
        ctx, _ = patch_search()
        with ctx:
            response = await client.get(
                "/external-bids", params={"numOfRows": 9999}
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_page_no_must_be_positive(self, client):
        ctx, _ = patch_search()
        with ctx:
            response = await client.get("/external-bids", params={"pageNo": 0})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_null_raw_becomes_empty_dict(self, client):
        ctx, _ = patch_search(rows=[notice_row(data=None)], total=1)
        with ctx:
            response = await client.get("/external-bids")

        assert response.json()["items"][0]["raw"] == {}


# ---------------------------------------------------------------------------
# 결과 조회
# ---------------------------------------------------------------------------

class TestSearchResults:
    @pytest.mark.asyncio
    async def test_returns_mapped_results(self, client):
        ctx, _ = patch_search(rows=[result_row()], total=1)
        with ctx:
            response = await client.get("/external-bids/results")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source"] == "kwater"
        assert item["sourceName"] == "한국수자원공사"
        assert item["bidderNm"] == "(주)동양화학"
        assert item["bidderAmt"] == 37086150

    @pytest.mark.asyncio
    async def test_notice_no_filter_passed_through(self, client):
        ctx, svc = patch_search()
        with ctx:
            await client.get(
                "/external-bids/results", params={"noticeNo": "B1"}
            )

        assert svc.search_results.await_args.kwargs["notice_no"] == "B1"

    @pytest.mark.asyncio
    async def test_unknown_source_is_rejected(self, client):
        ctx, _ = patch_search()
        with ctx:
            response = await client.get(
                "/external-bids/results", params={"source": "nope"}
            )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# 수동 동기화 (관리자)
# ---------------------------------------------------------------------------

class TestManualSync:
    @pytest.mark.asyncio
    async def test_triggers_sync_and_returns_call_count(self, client):
        sched = MagicMock()
        sched.sync_source_window = AsyncMock(return_value=4)
        with patch(
            "app.services.external_bid_sync_scheduler."
            "external_bid_sync_scheduler",
            sched,
        ):
            response = await client.post(
                "/external-bids/sync",
                params={
                    "source": "kdhc",
                    "windowStart": "202610120000",
                    "windowEnd": "202610122359",
                },
            )

        assert response.status_code == 202
        assert response.json() == {"source": "kdhc", "apiCalls": 4}

    @pytest.mark.asyncio
    async def test_unknown_source_is_rejected(self, client):
        response = await client.post(
            "/external-bids/sync",
            params={
                "source": "nope",
                "windowStart": "202610120000",
                "windowEnd": "202610122359",
            },
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_sync_failure_returns_502(self, client):
        sched = MagicMock()
        sched.sync_source_window = AsyncMock(side_effect=RuntimeError("boom"))
        with patch(
            "app.services.external_bid_sync_scheduler."
            "external_bid_sync_scheduler",
            sched,
        ):
            response = await client.post(
                "/external-bids/sync",
                params={
                    "source": "kdhc",
                    "windowStart": "202610120000",
                    "windowEnd": "202610122359",
                },
            )

        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_requires_admin_dependency(self):
        """관리자 의존성이 걸려 있어야 한다 (오버라이드 없으면 통과 불가)."""
        import inspect

        sig = inspect.signature(external_bids.trigger_external_sync)
        admin_param = sig.parameters["admin_user"]
        assert "get_admin_user" in repr(admin_param.default)
