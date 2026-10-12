"""외부기관 공통 XML 클라이언트 테스트.

픽스처는 모두 실제 API 응답을 그대로 저장한 것이다 (2026-10-12 수집).
문서와 실제 응답이 다른 지점들이 여기서 고정된다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.external_sources.base import (
    DataGoKrXmlClient,
    ExternalApiError,
    ExternalRateLimitError,
    decode_body,
    parse_xml_envelope,
)
from app.services.service_key_rotator import ServiceKeyRotator


def make_response(body: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = body
    resp.text = body.decode("utf-8", "replace")
    return resp


def patch_get(*responses):
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
# decode_body — EUC-KR 대응
# ---------------------------------------------------------------------------

class TestDecodeBody:
    def test_decodes_utf8_body(self):
        raw = '<?xml version="1.0" encoding="UTF-8"?><a>한글</a>'.encode("utf-8")
        assert "한글" in decode_body(raw)

    def test_decodes_euc_kr_body_per_prolog(self):
        """LH 응답은 EUC-KR. expat 이 EUC-KR 을 모르므로 직접 디코딩해야 한다."""
        raw = '<?xml version="1.0" encoding="EUC-KR"?><a>한글</a>'.encode("euc-kr")
        assert "한글" in decode_body(raw)

    def test_strips_xml_declaration(self):
        """str 에 encoding 선언이 남아 있으면 ElementTree 가 ValueError 를 낸다."""
        raw = '<?xml version="1.0" encoding="EUC-KR"?><a>x</a>'.encode("euc-kr")
        assert "<?xml" not in decode_body(raw)

    def test_falls_back_when_prolog_encoding_is_wrong(self):
        """prolog 는 EUC-KR 이라 하지만 실제로 UTF-8 인 경우에도 죽지 않는다."""
        raw = '<?xml version="1.0" encoding="EUC-KR"?><a>한글</a>'.encode("utf-8")
        assert "<a>" in decode_body(raw)

    def test_handles_missing_prolog(self):
        assert "<a>" in decode_body(b"<a>x</a>")


# ---------------------------------------------------------------------------
# parse_xml_envelope — 소스별 실제 응답 구조
# ---------------------------------------------------------------------------

class TestParseEnvelope:
    def test_standard_items_wrapper(self, fixture_bytes):
        env = parse_xml_envelope(fixture_bytes("kdhc_notices.xml"))

        assert env.code == "00"
        assert len(env.items) == 2
        assert env.items[0]["bidAnnoNo"]
        assert env.total_count > 0

    def test_lh_has_item_directly_under_body_without_items_wrapper(
        self, fixture_bytes
    ):
        """LH 는 <body><item> 구조 — <items> 래퍼가 없다. 실측 확인."""
        env = parse_xml_envelope(fixture_bytes("lh_notices.xml"))

        assert env.code == "00"
        assert len(env.items) >= 1
        assert env.items[0]["bidNum"]
        assert env.total_count > 0

    def test_lh_korean_text_decoded_correctly(self, fixture_bytes):
        env = parse_xml_envelope(fixture_bytes("lh_notices.xml"))
        title = env.items[0]["bidnmKor"]
        assert title and "�" not in title

    def test_empty_items_element_yields_no_items(self, fixture_bytes):
        """수자원 rstList 는 cntrctDivCd 누락 시 <items/> 로 온다."""
        env = parse_xml_envelope(fixture_bytes("kwater_rst.xml"))

        assert env.code == "00"
        assert env.items == ()
        assert env.total_count == 0

    def test_uppercase_tag_names_preserved(self, fixture_bytes):
        """가스공사 필드는 전부 대문자+언더스코어다."""
        env = parse_xml_envelope(fixture_bytes("kogas_notices.xml"))
        assert env.items[0]["NOTICE_CODE"]
        assert "NOTICE_NAME" in env.items[0]

    def test_empty_element_becomes_none(self, fixture_bytes):
        """가스공사 미낙찰 공고는 <SUCCESS_AMT/> 처럼 빈 엘리먼트로 온다."""
        env = parse_xml_envelope(fixture_bytes("kogas_notices.xml"))
        assert env.items[0]["SUCCESS_AMT"] is None

    def test_kra_mixed_case_tag_bcode(self, fixture_bytes):
        """문서는 bCode 지만 실제 응답은 BCode 다."""
        env = parse_xml_envelope(fixture_bytes("kra_notices.xml"))
        assert env.items[0]["BCode"]

    def test_kwater_items(self, fixture_bytes):
        env = parse_xml_envelope(fixture_bytes("kwater_cntrwk.xml"))
        assert env.items[0]["tndrPbanno"]
        assert env.items[0]["cntrctDivNm"] == "공사"

    def test_error_envelope_exposes_code_and_message(self):
        raw = (
            b'<response><header><resultCode>11</resultCode>'
            b'<resultMsg>NO MANDATORY REQUEST PARAMETERS ERROR.</resultMsg>'
            b'</header></response>'
        )
        env = parse_xml_envelope(raw)

        assert env.code == "11"
        assert "MANDATORY" in env.message

    def test_gateway_error_envelope(self):
        """data.go.kr 게이트웨이 에러는 cmmMsgHeader 봉투를 쓴다."""
        raw = (
            b'<OpenAPI_ServiceResponse><cmmMsgHeader>'
            b'<returnReasonCode>22</returnReasonCode>'
            b'<returnAuthMsg>LIMITED_NUMBER_OF_SERVICE_REQUESTS</returnAuthMsg>'
            b'</cmmMsgHeader></OpenAPI_ServiceResponse>'
        )
        env = parse_xml_envelope(raw)

        assert env.code == "22"

    def test_malformed_xml_raises(self):
        with pytest.raises(ExternalApiError) as exc:
            parse_xml_envelope(b"<response><unclosed>")
        assert exc.value.code == "PARSE"


# ---------------------------------------------------------------------------
# DataGoKrXmlClient — 로테이션 / 에러 전파
# ---------------------------------------------------------------------------

OK_BODY = (
    b'<response><header><resultCode>00</resultCode>'
    b'<resultMsg>NORMAL SERVICE.</resultMsg></header>'
    b'<body><items><item><a>1</a></item></items>'
    b'<totalCount>1</totalCount></body></response>'
)
QUOTA_BODY = (
    b'<OpenAPI_ServiceResponse><cmmMsgHeader>'
    b'<returnReasonCode>22</returnReasonCode>'
    b'<returnAuthMsg>quota</returnAuthMsg>'
    b'</cmmMsgHeader></OpenAPI_ServiceResponse>'
)
NO_DATA_BODY = (
    b'<response><header><resultCode>03</resultCode>'
    b'<resultMsg>NODATA_ERROR</resultMsg></header></response>'
)


@pytest.fixture
def client():
    return DataGoKrXmlClient(rotator=ServiceKeyRotator(["key1"]))


@pytest.fixture
def multikey_client():
    return DataGoKrXmlClient(rotator=ServiceKeyRotator(["key1", "key2", "key3"]))


class TestClientFetch:
    @pytest.mark.asyncio
    async def test_returns_items_on_success(self, client):
        with patch_get(make_response(OK_BODY)):
            env = await client.fetch("http://x", {}, "ctx")

        assert env is not None
        assert env.items[0]["a"] == "1"

    @pytest.mark.asyncio
    async def test_injects_service_key(self, client):
        with patch_get(make_response(OK_BODY)) as mock_get:
            await client.fetch("http://x", {"pageNo": 1}, "ctx")

        assert mock_get.call_args.kwargs["params"]["serviceKey"] == "key1"

    @pytest.mark.asyncio
    async def test_no_data_code_returns_none(self, client):
        with patch_get(make_response(NO_DATA_BODY)):
            assert await client.fetch("http://x", {}, "ctx") is None

    @pytest.mark.asyncio
    async def test_http_404_returns_none(self, client):
        with patch_get(make_response(b"", status_code=404)):
            assert await client.fetch("http://x", {}, "ctx") is None

    @pytest.mark.asyncio
    async def test_quota_code_rotates_then_succeeds(self, multikey_client):
        with patch_get(make_response(QUOTA_BODY), make_response(OK_BODY)):
            env = await multikey_client.fetch("http://x", {}, "ctx")

        assert env is not None
        assert multikey_client.rotator.active_idx == 1

    @pytest.mark.asyncio
    async def test_http_429_rotates_then_succeeds(self, multikey_client):
        with patch_get(
            make_response(b"rate limited", status_code=429),
            make_response(OK_BODY),
        ):
            env = await multikey_client.fetch("http://x", {}, "ctx")

        assert env is not None
        assert multikey_client.rotator.active_idx == 1

    @pytest.mark.asyncio
    async def test_bare_403_rotates_then_succeeds(self, multikey_client):
        """LOCAL 키는 외부기관 서비스에서 bare 403 을 반환한다 (실측)."""
        with patch_get(
            make_response(b"<html>Forbidden</html>", status_code=403),
            make_response(OK_BODY),
        ):
            env = await multikey_client.fetch("http://x", {}, "ctx")

        assert env is not None
        assert multikey_client.rotator.active_idx == 1

    @pytest.mark.asyncio
    async def test_all_keys_403_raises_with_hint(self, client):
        with patch_get(make_response(b"Forbidden", status_code=403)):
            with pytest.raises(ExternalApiError) as exc:
                await client.fetch("http://x", {}, "ctx")

        assert exc.value.code == "403"
        assert "활용신청" in str(exc.value)

    @pytest.mark.asyncio
    async def test_all_keys_exhausted_raises_rate_limit(self, multikey_client):
        with patch_get(*[make_response(QUOTA_BODY)] * 3):
            with pytest.raises(ExternalRateLimitError):
                await multikey_client.fetch("http://x", {}, "ctx")

    @pytest.mark.asyncio
    async def test_rate_limit_is_api_error_subclass(self):
        assert issubclass(ExternalRateLimitError, ExternalApiError)

    @pytest.mark.asyncio
    async def test_unknown_error_code_raises_not_swallowed(self, client):
        """에러를 빈 결과로 삼키면 동기화 윈도우가 0건으로 완료 마킹된다."""
        body = (
            b'<response><header><resultCode>11</resultCode>'
            b'<resultMsg>NO MANDATORY REQUEST PARAMETERS ERROR.</resultMsg>'
            b'</header></response>'
        )
        with patch_get(make_response(body)):
            with pytest.raises(ExternalApiError) as exc:
                await client.fetch("http://x", {}, "ctx")

        assert exc.value.code == "11"

    @pytest.mark.asyncio
    async def test_transport_error_raises(self, client):
        import httpx

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("boom"),
        ):
            with pytest.raises(ExternalApiError) as exc:
                await client.fetch("http://x", {}, "ctx")

        assert exc.value.code == "TRANSPORT"


def make_page(count: int, total: int) -> bytes:
    items = b"".join(
        f"<item><a>{i}</a></item>".encode() for i in range(count)
    )
    return (
        b'<response><header><resultCode>00</resultCode>'
        b'<resultMsg>NORMAL SERVICE.</resultMsg></header><body><items>'
        + items
        + b'</items><totalCount>' + str(total).encode()
        + b'</totalCount></body></response>'
    )


class TestFetchPaged:
    @pytest.mark.asyncio
    async def test_single_short_page_stops_immediately(self, client):
        with patch_get(make_response(make_page(1, 1))) as mock_get:
            items, calls = await client.fetch_paged(
                "http://x", {}, "ctx", page_size=2
            )

        assert len(items) == 1
        assert calls == 1
        assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_follows_pages_until_short_page(self, client):
        with patch_get(
            make_response(make_page(2, 3)),
            make_response(make_page(1, 3)),
        ):
            items, calls = await client.fetch_paged(
                "http://x", {}, "ctx", page_size=2
            )

        assert len(items) == 3
        assert calls == 2

    @pytest.mark.asyncio
    async def test_stops_when_total_count_reached(self, client):
        """full page 인데 totalCount 를 채웠으면 더 요청하지 않는다."""
        with patch_get(make_response(make_page(2, 2))):
            items, calls = await client.fetch_paged(
                "http://x", {}, "ctx", page_size=2
            )

        assert len(items) == 2
        assert calls == 1

    @pytest.mark.asyncio
    async def test_sends_page_and_size_params(self, client):
        with patch_get(make_response(make_page(1, 1))) as mock_get:
            await client.fetch_paged("http://x", {"k": "v"}, "ctx", page_size=7)

        params = mock_get.call_args.kwargs["params"]
        assert params["pageNo"] == 1
        assert params["numOfRows"] == 7
        assert params["k"] == "v"

    @pytest.mark.asyncio
    async def test_no_data_returns_empty(self, client):
        with patch_get(make_response(NO_DATA_BODY)):
            items, calls = await client.fetch_paged("http://x", {}, "ctx")

        assert items == ()
        assert calls == 1

    @pytest.mark.asyncio
    async def test_error_propagates_instead_of_partial_result(self, client):
        """2페이지 실패 시 1페이지 결과를 성공으로 돌려주면 누락이 영구화된다."""
        with patch_get(
            make_response(make_page(2, 99)),
            make_response(
                b'<response><header><resultCode>11</resultCode>'
                b'<resultMsg>bad</resultMsg></header></response>'
            ),
        ):
            with pytest.raises(ExternalApiError):
                await client.fetch_paged("http://x", {}, "ctx", page_size=2)

    @pytest.mark.asyncio
    async def test_max_pages_cap_is_logged(self, client, caplog):
        full = make_response(make_page(2, 10_000))
        with patch_get(*[full] * 4):
            items, calls = await client.fetch_paged(
                "http://x", {}, "ctx", page_size=2, max_pages=3
            )

        assert calls == 3
        assert len(items) == 6
        assert "max_pages" in caplog.text
