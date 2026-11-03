"""이메일 템플릿 렌더링 테스트 (HTML 주입 방지, 이상값 내성)."""
from unittest.mock import AsyncMock

import pytest

from app.schemas.bid import BidItem
from app.services.email_service import EmailService, format_won

XSS = "<script>alert(1)</script>"


def bid(**kw):
    base = dict(bidNtceNo="R1", bidNtceOrd="000", bidNtceNm="공고", ntceInsttNm="기관")
    base.update(kw)
    return BidItem(**base)


@pytest.fixture
def service():
    svc = EmailService()
    svc.send_email = AsyncMock(return_value=True)
    return svc


class TestHtmlEscaping:
    @pytest.mark.asyncio
    async def test_notification_html_escapes_untrusted_fields(self, service):
        notices = [bid(bidNtceNm=XSS, ntceInsttNm='<img src=x onerror="a()">')]
        assert await service.send_bid_notification("a@b.kr", XSS, notices) is True

        kwargs = service.send_email.await_args.kwargs
        html, text = kwargs["html_content"], kwargs["text_content"]
        assert XSS not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<img src=x" not in html
        # plain text 파트는 이스케이프하지 않는다 (HTML 이 아님)
        assert XSS in text

    @pytest.mark.asyncio
    async def test_welcome_html_escapes_username(self, service):
        await service.send_welcome_email("a@b.kr", XSS)
        html = service.send_email.await_args.kwargs["html_content"]
        assert XSS not in html and "&lt;script&gt;" in html

    @pytest.mark.asyncio
    async def test_normal_content_still_renders(self, service):
        await service.send_bid_notification(
            "a@b.kr", "홍길동", [bid(presmptPrce="1234567", bidClseDt="202611051800")]
        )
        html = service.send_email.await_args.kwargs["html_content"]
        assert "홍길동" in html and "1,234,567원" in html and "202611051800" in html


class TestPriceGuard:
    @pytest.mark.parametrize(
        "value,expected",
        [("1234567", "1,234,567"), ("1,234", "1,234"), (5000, "5,000"), ("12.7", "12"),
         (None, "0"), ("", "0"), ("abc", "0"), ("inf", "0"), ("nan", "0"), ([], "0")],
    )
    def test_format_won(self, value, expected):
        assert format_won(value) == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["abc", "inf", None, "미정"])
    async def test_bad_price_does_not_kill_email(self, service, bad):
        notices = [bid(presmptPrce=bad), bid(bidNtceNo="R2", presmptPrce="1000")]
        assert await service.send_bid_notification("a@b.kr", "u", notices) is True
        assert "1,000원" in service.send_email.await_args.kwargs["html_content"]


class TestLogging:
    @pytest.mark.asyncio
    async def test_send_failure_logs_instead_of_print(self, caplog, capsys):
        svc = EmailService()
        svc.smtp_host = "127.0.0.1"
        svc.smtp_port = 1
        with caplog.at_level("ERROR"):
            assert await svc.send_email("a@b.kr", "s", "<p>x</p>") is False
        assert "Failed to send email" in caplog.text
        assert capsys.readouterr().out == ""
