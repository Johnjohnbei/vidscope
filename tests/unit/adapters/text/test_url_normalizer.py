"""Unit tests for :func:`vidscope.adapters.text.url_normalizer.normalize_url`.

Covers the 10 behaviours specified in M007/S02-P02 §T01, plus
additional edge cases for robustness.
"""

from __future__ import annotations

from vidscope.adapters.text.url_normalizer import normalize_url


class TestNormalizeUrl:
    """Core normalization rules (Tests 1-10 from the plan)."""

    def test_strip_trailing_slash(self) -> None:
        """Test 1: trailing slash removed from root."""
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_lowercase_scheme_and_host_preserves_path_case(self) -> None:
        """Test 2: scheme + host lowercased, path case preserved."""
        assert normalize_url("HTTPS://Example.COM/PATH") == "https://example.com/PATH"

    def test_sort_query_params_alphabetically(self) -> None:
        """Test 3: query params sorted by key."""
        assert normalize_url("https://example.com/?b=2&a=1") == "https://example.com/?a=1&b=2"

    def test_strip_utm_source(self) -> None:
        """Test 4: utm_source stripped, other params kept."""
        assert normalize_url("https://example.com/?utm_source=tiktok&id=42") == "https://example.com/?id=42"

    def test_strip_fragment(self) -> None:
        """Test 5: fragment stripped entirely."""
        assert normalize_url("https://example.com/#fragment") == "https://example.com"

    def test_strip_all_utm_params(self) -> None:
        """Test 6: all utm_* params stripped, non-utm kept."""
        result = normalize_url(
            "https://example.com/?utm_source=x&utm_medium=y&utm_campaign=z&id=1"
        )
        assert result == "https://example.com/?id=1"

    def test_idempotence_on_multiple_urls(self) -> None:
        """Test 7: normalize_url(normalize_url(url)) == normalize_url(url) for many URLs."""
        urls = [
            "https://example.com/",
            "HTTPS://Example.COM/PATH",
            "https://example.com/?b=2&a=1",
            "https://example.com/?utm_source=tiktok&id=42",
            "https://example.com/#fragment",
            "https://example.com/?utm_source=x&utm_medium=y&id=1",
            "https://www.example.com/path",
            "http://example.com",
            "https://example.com",
            "bit.ly/abc",
            "https://shop.com/product?id=1&utm_source=ig#frag",
        ]
        for url in urls:
            normalized = normalize_url(url)
            assert normalize_url(normalized) == normalized, (
                f"normalize_url is not idempotent for {url!r}: "
                f"normalize(normalize(url))={normalize_url(normalized)!r}"
                f" != normalize(url)={normalized!r}"
            )

    def test_www_preserved(self) -> None:
        """Test 8: www. prefix is preserved (no www-stripping in M007)."""
        assert normalize_url("https://www.example.com/path") == "https://www.example.com/path"

    def test_scheme_distinction_preserved(self) -> None:
        """Test 9: http and https remain distinct."""
        http = normalize_url("http://example.com")
        https = normalize_url("https://example.com")
        assert http != https
        assert http == "http://example.com"
        assert https == "https://example.com"

    def test_bare_domain_prepends_https(self) -> None:
        """Test 10: bare domain without scheme gets https:// prepended."""
        assert normalize_url("bit.ly/abc") == "https://bit.ly/abc"

    # Additional edge cases

    def test_empty_string_returns_empty(self) -> None:
        assert normalize_url("") == ""

    def test_whitespace_only_returns_empty(self) -> None:
        assert normalize_url("   ") == ""

    def test_complex_url_all_rules(self) -> None:
        """Multiple rules applied simultaneously."""
        result = normalize_url(
            "HTTPS://Example.COM/PATH/?utm_source=x&b=2&a=1#frag"
        )
        assert result == "https://example.com/PATH?a=1&b=2"

    def test_utm_case_insensitive_stripping(self) -> None:
        """UTM keys with mixed case are still stripped."""
        result = normalize_url("https://example.com/?UTM_SOURCE=x&id=1")
        assert result == "https://example.com/?id=1"

    def test_no_query_string_stays_clean(self) -> None:
        assert normalize_url("https://example.com/path") == "https://example.com/path"

    def test_port_preserved(self) -> None:
        result = normalize_url("https://api.example.com:8080/endpoint")
        assert result == "https://api.example.com:8080/endpoint"
