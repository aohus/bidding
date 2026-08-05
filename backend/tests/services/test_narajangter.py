from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.bid import BidSearchParams
from app.services.narajangter import (
    KEY_RESET_SECONDS,
    NaraJangterApiError,
    NaraJangterService,
    RateLimitError,
    _extract_error,
    _items_of,
)
from tests.conftest import (
    make_error_response,
    make_gateway_error_response,
    make_mock_response,
    make_service_error_response,
    make_success_response,
)


@pytest.fixture
def service():
    svc = NaraJangterService()
    svc._service_keys = ["key1"]
    svc._active_key_idx = 0
    svc._rotated_at = None
    return svc


@pytest.fixture
def multikey_service():
    svc = NaraJangterService()
    svc._service_keys = ["key1", "key2", "key3"]
    svc._active_key_idx = 0
    svc._rotated_at = None
    return svc


def patch_get(*responses):
    """httpx.AsyncClient.get 을 순차 응답으로 패치합니다."""
    if len(responses) == 1:
        return patch(
            "httpx.AsyncClient.get", new_callable=AsyncMock,
            return_value=responses[0],
        )
    return patch(
        "httpx.AsyncClient.get", new_callable=AsyncMock,
        side_effect=list(responses),
    )


# ---------------------------------------------------------------------------
# Class constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_max_page_size_exists(self):
        assert NaraJangterService.MAX_PAGE_SIZE == 999

    def test_default_timeout_exists(self):
        assert NaraJangterService.DEFAULT_TIMEOUT_SECONDS == 30.0

    def test_single_notice_lookup_uses_plain_endpoints(self):
        """단건 조회는 PPSSrch 가 아닌 목록조회(일반) 엔드포인트여야 한다.

        PPSSrch 는 inqryDiv=2 가 '개찰일시'이고 bidNtceNo 를 무시한다.
        """
        assert NaraJangterService.PLAIN_CNST_URL.endswith(
            "getBidPblancListInfoCnstwk"
        )
        assert NaraJangterService.PLAIN_SERV_URL.endswith(
            "getBidPblancListInfoServc"
        )
        assert "PPSSrch" not in NaraJangterService.PLAIN_CNST_URL
        assert "PPSSrch" not in NaraJangterService.PLAIN_SERV_URL


# ---------------------------------------------------------------------------
# _extract_error — 세 가지 응답 봉투
# ---------------------------------------------------------------------------

class TestExtractError:
    def test_success_returns_none(self):
        assert _extract_error(make_success_response([])) is None

    def test_standard_envelope_error(self):
        code, msg = _extract_error(make_error_response("99", "BOOM"))
        assert code == "99"
        assert msg == "BOOM"

    def test_service_error_envelope(self):
        """조달청 자체 검증 에러 (조회기간 초과 등)."""
        code, msg = _extract_error(make_service_error_response("07"))
        assert code == "07"
        assert "입력범위값" in msg

    def test_gateway_error_envelope_quota(self):
        """일일 한도 초과는 게이트웨이 봉투 + 코드 22 로 온다."""
        code, msg = _extract_error(make_gateway_error_response("22"))
        assert code == "22"

    def test_gateway_error_envelope_bad_key(self):
        code, msg = _extract_error(
            make_gateway_error_response("30", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
        )
        assert code == "30"

    def test_unknown_envelope(self):
        code, _ = _extract_error({"something": "else"})
        assert code == "PARSE"

    def test_non_dict(self):
        code, _ = _extract_error(["not", "a", "dict"])
        assert code == "PARSE"


# ---------------------------------------------------------------------------
# _items_of
# ---------------------------------------------------------------------------

class TestItemsOf:
    def test_list_items(self):
        items, body = _items_of(make_success_response([{"bidNtceNo": "A"}]))
        assert items == [{"bidNtceNo": "A"}]
        assert "totalCount" in body

    def test_single_dict_normalized_to_list(self):
        items, _ = _items_of(make_success_response({"bidNtceNo": "B"}))
        assert items == [{"bidNtceNo": "B"}]

    def test_none_items(self):
        data = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": None, "totalCount": 0},
            }
        }
        items, _ = _items_of(data)
        assert items == []

    def test_missing_body(self):
        data = {"response": {"header": {"resultCode": "00"}}}
        items, body = _items_of(data)
        assert items == []
        assert body == {}


# ---------------------------------------------------------------------------
# _request — 키 로테이션 / 에러 분류
# ---------------------------------------------------------------------------

class TestRequestRotation:
    @pytest.mark.asyncio
    async def test_http_429_rotates_then_succeeds(self, multikey_service):
        limited = make_mock_response(status_code=429, text="rate limited")
        ok = make_mock_response(json_data=make_success_response([{"bidNtceNo": "X"}]))

        with patch_get(limited, ok):
            result = await multikey_service.get_bid_opening_results("X")

        assert len(result) == 1
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_code_22_rotates_then_succeeds(self, multikey_service):
        """일일 한도(코드 22)도 429 와 동일하게 로테이션 대상이다."""
        quota = make_mock_response(json_data=make_gateway_error_response("22"))
        ok = make_mock_response(json_data=make_success_response([{"bidNtceNo": "X"}]))

        with patch_get(quota, ok):
            result = await multikey_service.get_bid_opening_results("X")

        assert len(result) == 1
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_all_keys_exhausted_raises_rate_limit(self, multikey_service):
        quota = make_mock_response(json_data=make_gateway_error_response("22"))

        with patch_get(quota, quota, quota):
            with pytest.raises(RateLimitError) as exc:
                await multikey_service.get_bid_opening_results("X")

        assert multikey_service._active_key_idx == 2
        assert "exhausted" in str(exc.value)

    @pytest.mark.asyncio
    async def test_single_key_429_raises_immediately(self, service):
        limited = make_mock_response(status_code=429, text="rate limited")

        with patch_get(limited):
            with pytest.raises(RateLimitError):
                await service.get_bid_opening_results("X")

    @pytest.mark.asyncio
    async def test_bad_key_code_30_raises_with_hint(self, service):
        bad = make_mock_response(
            status_code=403,
            json_data=make_gateway_error_response(
                "30", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"
            ),
        )

        with patch_get(bad):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")

        assert exc.value.code == "30"
        assert "디코딩" in str(exc.value)

    @pytest.mark.asyncio
    async def test_rate_limit_error_is_api_error_subclass(self):
        assert issubclass(RateLimitError, NaraJangterApiError)

    def test_key_reset_after_24h(self, multikey_service):
        multikey_service._active_key_idx = 2
        multikey_service._rotated_at = datetime.now(timezone.utc) - timedelta(
            seconds=KEY_RESET_SECONDS + 60
        )

        multikey_service._maybe_reset_key()

        assert multikey_service._active_key_idx == 0
        assert multikey_service._rotated_at is None

    def test_key_not_reset_before_24h(self, multikey_service):
        multikey_service._active_key_idx = 2
        multikey_service._rotated_at = datetime.now(timezone.utc) - timedelta(
            seconds=KEY_RESET_SECONDS - 60
        )

        multikey_service._maybe_reset_key()

        assert multikey_service._active_key_idx == 2

    def test_rotate_records_timestamp(self, multikey_service):
        assert multikey_service._rotated_at is None
        assert multikey_service._rotate_key() is True
        assert multikey_service._rotated_at is not None

    def test_rotate_exhausted_returns_false(self, service):
        assert service._rotate_key() is False

    def test_missing_key_config_raises(self):
        svc = NaraJangterService()
        svc._service_keys = []
        with pytest.raises(NaraJangterApiError) as exc:
            svc._active_key()
        assert exc.value.code == "CONFIG"


# ---------------------------------------------------------------------------
# _request — 데이터 없음 vs 에러 구분
# ---------------------------------------------------------------------------

class TestRequestNoDataVsError:
    @pytest.mark.asyncio
    async def test_http_404_is_no_data(self, service):
        resp = make_mock_response(status_code=404, text="not found")
        with patch_get(resp):
            assert await service.get_bid_opening_results("X") == []

    @pytest.mark.asyncio
    async def test_result_code_03_is_no_data(self, service):
        resp = make_mock_response(json_data=make_error_response("03", "NODATA"))
        with patch_get(resp):
            assert await service.get_bid_opening_results("X") == []

    @pytest.mark.asyncio
    async def test_generic_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("01", "App Error"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")
        assert exc.value.code == "01"

    @pytest.mark.asyncio
    async def test_non_json_raises(self, service):
        resp = make_mock_response(json_raises=True, text="<html>gateway</html>")
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_bid_opening_results("X")
        assert exc.value.code == "PARSE"

    @pytest.mark.asyncio
    async def test_unknown_envelope_raises(self, service):
        resp = make_mock_response(json_data={"unexpected": 1})
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_bid_opening_results("X")


# ---------------------------------------------------------------------------
# get_bid_notice_by_no — 단건 조회
# ---------------------------------------------------------------------------

class TestGetBidNoticeByNo:
    @pytest.mark.asyncio
    async def test_uses_plain_endpoint_and_inqrydiv_2(self, service):
        item = {
            "bidNtceNo": "R26BK01665863",
            "bidNtceOrd": "000",
            "bidNtceNm": "테스트 공고",
            "ntceInsttNm": "경기도 양평군",
        }
        resp = make_mock_response(json_data=make_success_response([item]))

        with patch_get(resp) as mock_get:
            result = await service.get_bid_notice_by_no("R26BK01665863")

            url = mock_get.call_args[0][0]
            params = mock_get.call_args[1]["params"]

        assert result is not None
        assert result.bidNtceNo == "R26BK01665863"
        assert url == NaraJangterService.PLAIN_CNST_URL
        assert params["inqryDiv"] == "2"
        assert params["bidNtceNo"] == "R26BK01665863"

    @pytest.mark.asyncio
    async def test_does_not_send_date_range(self, service):
        """조회기간을 보내면 안 된다 — 1개월 초과 시 resultCode 07 로 실패한다.

        기존 구현은 2025-01-01~2027-12-31 을 보내 항상 실패했다.
        """
        resp = make_mock_response(json_data=make_success_response([]))

        with patch_get(resp) as mock_get:
            await service.get_bid_notice_by_no("R26BK01665863")
            params = mock_get.call_args[1]["params"]

        assert "inqryBgnDt" not in params
        assert "inqryEndDt" not in params

    @pytest.mark.asyncio
    async def test_service_type_uses_plain_serv_url(self, service):
        resp = make_mock_response(json_data=make_success_response([]))

        with patch_get(resp) as mock_get:
            await service.get_bid_notice_by_no("X", bid_type="servc")
            url = mock_get.call_args[0][0]

        assert url == NaraJangterService.PLAIN_SERV_URL

    @pytest.mark.asyncio
    async def test_no_exact_match_returns_none(self, service):
        """다른 공고가 섞여 와도 첫 항목으로 폴백하면 안 된다.

        폴백하면 엉뚱한 공고 데이터가 그 공고번호로 저장된다.
        """
        others = [
            {
                "bidNtceNo": "R26BK09999999",
                "bidNtceOrd": "000",
                "bidNtceNm": "다른 공고",
                "ntceInsttNm": "다른 기관",
            }
        ]
        resp = make_mock_response(json_data=make_success_response(others))

        with patch_get(resp):
            result = await service.get_bid_notice_by_no("R26BK01665863")

        assert result is None

    @pytest.mark.asyncio
    async def test_picks_exact_match_among_many(self, service):
        items = [
            {
                "bidNtceNo": "R26BK00000001",
                "bidNtceOrd": "000",
                "bidNtceNm": "A",
                "ntceInsttNm": "기관",
            },
            {
                "bidNtceNo": "R26BK01665863",
                "bidNtceOrd": "000",
                "bidNtceNm": "정답",
                "ntceInsttNm": "기관",
            },
        ]
        resp = make_mock_response(json_data=make_success_response(items))

        with patch_get(resp):
            result = await service.get_bid_notice_by_no("R26BK01665863")

        assert result is not None
        assert result.bidNtceNm == "정답"

    @pytest.mark.asyncio
    async def test_empty_result_returns_none(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp):
            assert await service.get_bid_notice_by_no("X") is None

    @pytest.mark.asyncio
    async def test_parses_v12_new_fields(self, service):
        """참고자료 v1.2 신규 항목이 스키마에 담겨야 한다."""
        item = {
            "bidNtceNo": "R26BK01665863",
            "bidNtceOrd": "000",
            "bidNtceNm": "테스트",
            "ntceInsttNm": "기관",
            "sucsfbidMthdAppStd": "지방자치단체 입찰시 낙찰자 결정기준",
            "befBidBbancNo": "R26BK01660000",
        }
        resp = make_mock_response(json_data=make_success_response([item]))

        with patch_get(resp):
            result = await service.get_bid_notice_by_no("R26BK01665863")

        assert result.sucsfbidMthdAppStd == "지방자치단체 입찰시 낙찰자 결정기준"
        assert result.befBidBbancNo == "R26BK01660000"


# ---------------------------------------------------------------------------
# get_bid_a_value
# ---------------------------------------------------------------------------

class TestGetBidAValue:
    @pytest.mark.asyncio
    async def test_success_cnstwk(self, service):
        items = [{"bidNtceNo": "20240209001", "bssamt": "1000000000"}]
        resp = make_mock_response(json_data=make_success_response(items))

        with patch_get(resp) as mock_get:
            result = await service.get_bid_a_value("20240209001", bid_type="cnstwk")
            url = mock_get.call_args[0][0]

        assert result.bssamt == "1000000000"
        assert url == NaraJangterService.CNSTWK_BSSAMT_URL

    @pytest.mark.asyncio
    async def test_success_servc_uses_servc_url(self, service):
        items = [{"bidNtceNo": "20240209002", "bssamt": "500000000"}]
        resp = make_mock_response(json_data=make_success_response(items))

        with patch_get(resp) as mock_get:
            result = await service.get_bid_a_value("20240209002", bid_type="servc")
            url = mock_get.call_args[0][0]

        assert result.bidNtceNo == "20240209002"
        assert url == NaraJangterService.SERVC_BSSAMT_URL

    @pytest.mark.asyncio
    async def test_404_returns_none(self, service):
        resp = make_mock_response(status_code=404)
        with patch_get(resp):
            assert await service.get_bid_a_value("NOTFOUND") is None

    @pytest.mark.asyncio
    async def test_rate_limit_raises_not_silently_none(self, service):
        """한도 소진을 None 으로 삼키면 호출자가 '데이터 없음'과 구분할 수 없다."""
        limited = make_mock_response(status_code=429)
        with patch_get(limited):
            with pytest.raises(RateLimitError):
                await service.get_bid_a_value("RATELIMITED")

    @pytest.mark.asyncio
    async def test_empty_items_returns_none(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp):
            assert await service.get_bid_a_value("EMPTY") is None

    @pytest.mark.asyncio
    async def test_single_dict_item(self, service):
        data = make_success_response({"bidNtceNo": "SINGLE", "bssamt": "100"})
        resp = make_mock_response(json_data=data)
        with patch_get(resp):
            result = await service.get_bid_a_value("SINGLE")
        assert result.bidNtceNo == "SINGLE"


# ---------------------------------------------------------------------------
# 날짜 기준 대량 조회 — 에러를 빈 결과로 삼키지 않아야 한다
# ---------------------------------------------------------------------------

class TestBulkDateFetchersAreStrict:
    """이 계열이 에러를 [] 로 반환하면 동기화 윈도우가 0건으로 완료 마킹되어
    해당 구간 데이터가 영구 누락된다."""

    @pytest.mark.asyncio
    async def test_regions_success(self, service):
        items = [{"bidNtceNo": "B001", "bidNtceOrd": "000", "prtcptPsblRgnNm": "서울"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp):
            result = await service.get_prtcpt_psbl_rgn_by_date("x", "y")
        assert result[0].bidNtceNo == "B001"

    @pytest.mark.asyncio
    async def test_regions_rate_limit_raises(self, service):
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.get_prtcpt_psbl_rgn_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_regions_quota_code_raises(self, service):
        resp = make_mock_response(json_data=make_gateway_error_response("22"))
        with patch_get(resp):
            with pytest.raises(RateLimitError):
                await service.get_prtcpt_psbl_rgn_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_regions_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("02", "DB Error"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_prtcpt_psbl_rgn_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_regions_default_num_of_rows_is_999(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp) as mock_get:
            await service.get_prtcpt_psbl_rgn_by_date("x", "y")
            params = mock_get.call_args[1]["params"]
        assert params["numOfRows"] == 999

    @pytest.mark.asyncio
    async def test_license_success(self, service):
        items = [{"bidNtceNo": "L001", "lcnsLmtNm": "건설업"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp):
            result = await service.get_license_limit_by_date("x", "y")
        assert result[0].bidNtceNo == "L001"

    @pytest.mark.asyncio
    async def test_license_rate_limit_raises(self, service):
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.get_license_limit_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_license_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("07", "범위초과"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.get_license_limit_by_date("x", "y")

    @pytest.mark.asyncio
    async def test_license_service_error_envelope_raises(self, service):
        resp = make_mock_response(json_data=make_service_error_response("07"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError) as exc:
                await service.get_license_limit_by_date("x", "y")
        assert exc.value.code == "07"


# ---------------------------------------------------------------------------
# get_prtcpt_psbl_rgn_by_bid
# ---------------------------------------------------------------------------

class TestGetPrtcptPsblRgnByBid:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [{"bidNtceNo": "B001", "bidNtceOrd": "000", "prtcptPsblRgnNm": "경기"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp) as mock_get:
            result = await service.get_prtcpt_psbl_rgn_by_bid("B001")
            params = mock_get.call_args[1]["params"]

        assert result[0].prtcptPsblRgnNm == "경기"
        # 부속 데이터 엔드포인트는 inqryDiv=2 + bidNtceNo 필터가 정상 동작한다.
        assert params["inqryDiv"] == 2
        assert params["bidNtceNo"] == "B001"

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, service):
        with patch_get(make_mock_response(status_code=404)):
            assert await service.get_prtcpt_psbl_rgn_by_bid("NOTFOUND") == []

    @pytest.mark.asyncio
    async def test_rate_limit_raises(self, service):
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.get_prtcpt_psbl_rgn_by_bid("X")


# ---------------------------------------------------------------------------
# get_bid_opening_results
# ---------------------------------------------------------------------------

class TestGetBidOpeningResults:
    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [{"bidNtceNo": "R001", "opengRank": "1", "prcbdrNm": "회사"}]
        resp = make_mock_response(json_data=make_success_response(items))
        with patch_get(resp):
            result = await service.get_bid_opening_results("R001")
        assert result[0].prcbdrNm == "회사"

    @pytest.mark.asyncio
    async def test_num_of_rows_passed_through(self, service):
        resp = make_mock_response(json_data=make_success_response([]))
        with patch_get(resp) as mock_get:
            await service.get_bid_opening_results("X", numOfRows=50)
            params = mock_get.call_args[1]["params"]
        assert params["numOfRows"] == 50


# ---------------------------------------------------------------------------
# search_bids
# ---------------------------------------------------------------------------

class TestSearchBids:
    def _params(self, **kw):
        base = dict(
            inqryDiv="1",
            inqryBgnDt="202608040000",
            inqryEndDt="202608042359",
            numOfRows=100,
            pageNo=1,
        )
        base.update(kw)
        return BidSearchParams(**base)

    @pytest.mark.asyncio
    async def test_success(self, service):
        items = [
            {
                "bidNtceNo": "R26BK01665863",
                "bidNtceOrd": "000",
                "bidNtceNm": "공고",
                "ntceInsttNm": "기관",
            }
        ]
        resp = make_mock_response(json_data=make_success_response(items, 1))
        with patch_get(resp):
            result = await service.search_bids("contract", self._params())

        assert result.totalCount == 1
        assert result.items[0].bidNtceNo == "R26BK01665863"

    @pytest.mark.asyncio
    async def test_uses_ppssrch_endpoint(self, service):
        resp = make_mock_response(json_data=make_success_response([], 0))
        with patch_get(resp) as mock_get:
            await service.search_bids("contract", self._params())
            url = mock_get.call_args[0][0]
        assert url == NaraJangterService.BASE_CNST_URL

    @pytest.mark.asyncio
    async def test_api_error_raises(self, service):
        resp = make_mock_response(json_data=make_error_response("01", "App Error"))
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.search_bids("contract", self._params())

    @pytest.mark.asyncio
    async def test_rate_limit_raises(self, service):
        """공고 조회도 한도 소진 시 RateLimitError 여야 한다.

        기존 구현은 여기에 키 로테이션이 없어, V1 한도가 끝나면 V2~V4 가
        남아 있어도 공고 수집 전체가 죽었다.
        """
        with patch_get(make_mock_response(status_code=429)):
            with pytest.raises(RateLimitError):
                await service.search_bids("contract", self._params())

    @pytest.mark.asyncio
    async def test_rate_limit_rotates_key(self, multikey_service):
        limited = make_mock_response(status_code=429)
        ok = make_mock_response(json_data=make_success_response([], 0))
        with patch_get(limited, ok):
            await multikey_service.search_bids("contract", self._params())
        assert multikey_service._active_key_idx == 1

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, service):
        resp = make_mock_response(json_raises=True, text="boom")
        with patch_get(resp):
            with pytest.raises(NaraJangterApiError):
                await service.search_bids("contract", self._params())

    @pytest.mark.asyncio
    async def test_optional_filters_passed(self, service):
        resp = make_mock_response(json_data=make_success_response([], 0))
        params = self._params(prtcptLmtRgnNm="경기도", indstrytyNm="조경식재")
        with patch_get(resp) as mock_get:
            await service.search_bids("contract", params)
            q = mock_get.call_args[1]["params"]
        assert q["prtcptLmtRgnNm"] == "경기도"
        assert q["indstrytyNm"] == "조경식재"

    @pytest.mark.asyncio
    async def test_no_data_returns_empty_response(self, service):
        resp = make_mock_response(json_data=make_error_response("03", "NODATA"))
        with patch_get(resp):
            result = await service.search_bids("contract", self._params())
        assert result.items == []
        assert result.totalCount == 0
