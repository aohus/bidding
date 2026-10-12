"""서비스키 정규화 / 키 풀 구성 테스트.

실측 배경:
- data.go.kr 의 '인코딩' 키를 그대로 serviceKey 로 보내면 이중 인코딩되어
  HTTP 403 또는 resultCode 30 이 된다. 반드시 '디코딩' 키를 써야 한다.
- 운영 .env 에 인코딩 키가 들어있던 사례가 실제로 있었으므로(96자, '%' 포함)
  로드 시점에 방어적으로 정규화한다.
"""

from app.core.config import build_key_pool, normalize_service_key


class TestNormalizeServiceKey:
    def test_returns_decoded_key_unchanged(self):
        key = "abc+def/ghi=="
        assert normalize_service_key(key) == key

    def test_url_decodes_an_encoded_key(self):
        assert normalize_service_key("abc%2Bdef%2Fghi%3D%3D") == "abc+def/ghi=="

    def test_strips_surrounding_whitespace(self):
        assert normalize_service_key("  abc123  ") == "abc123"

    def test_empty_string_stays_empty(self):
        assert normalize_service_key("") == ""

    def test_none_becomes_empty(self):
        assert normalize_service_key(None) == ""

    def test_bare_percent_is_not_treated_as_escape(self):
        # '%' 뒤에 16진수 2자리가 없으면 인코딩 키가 아니므로 그대로 둔다.
        # (실제 data.go.kr 디코딩 키는 base64 문자셋이라 '%' 를 포함하지 않는다.)
        assert normalize_service_key("abc%zz") == "abc%zz"


class TestBuildKeyPool:
    def test_preserves_order(self):
        assert build_key_pool("a", "b", "c") == ["a", "b", "c"]

    def test_drops_empty_and_none_entries(self):
        assert build_key_pool("a", "", None, "b") == ["a", "b"]

    def test_deduplicates_keeping_first_occurrence(self):
        assert build_key_pool("a", "b", "a") == ["a", "b"]

    def test_deduplicates_encoded_and_decoded_form_of_same_key(self):
        """PUBLIC_INST_SERVICE_KEY 가 NARAJANGTER 키의 인코딩 사본이었던 실제 사례."""
        assert build_key_pool("abc+def==", "abc%2Bdef%3D%3D") == ["abc+def=="]

    def test_empty_input_returns_empty_list(self):
        assert build_key_pool() == []
