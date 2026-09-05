"""Offline URL semantics and conservative-cleaning regressions."""
from __future__ import annotations

from urllib.parse import quote

import pytest

from cleaners import DEFAULT_REGISTRY, CleanerRegistry, CleanerService, deep_clean, preprocess
from cleaners.base import CleanerCategory, CleanerUtils
from cleaners.impl import build_default_registry
from cleaners.impl.general import GeneralTrackingCleaner
from cleaners.impl.google_search import GoogleSearchCleaner


def test_cleaner_failure_logs_only_type_and_processing_continues(caplog) -> None:
    secret = "SYNTHETIC_SECRET_987"
    url = f"https://private.example/reset?token={secret}&utm_source=tracking"

    class FailingCleaner:
        id = "synthetic_failing_cleaner"
        category = CleanerCategory.OTHER

        def matches(self, candidate: str) -> bool:
            return True

        def clean(self, candidate: str) -> str:
            raise ValueError(f"Could not process private URL {candidate}")

    registry = CleanerRegistry()
    registry.register_all([FailingCleaner(), GeneralTrackingCleaner])
    assert CleanerService(registry).deep_clean(url) == url.removesuffix("&utm_source=tracking")
    assert "synthetic_failing_cleaner" in caplog.text
    assert "ValueError" in caplog.text
    assert secret not in caplog.text
    assert "private.example" not in caplog.text
    assert "Could not process private URL" not in caplog.text
    assert caplog.records and all(record.exc_info is None for record in caplog.records)


def test_cache_failure_logs_only_type_and_returns_cleaned_result(caplog) -> None:
    secret = "SYNTHETIC_CACHE_SECRET_456"
    url = f"https://private.example/reset?token={secret}&utm_source=tracking"

    def failing_cache_set(original: str, cleaned: str) -> None:
        raise RuntimeError(f"Could not cache {original} -> {cleaned}")

    service = CleanerService(build_default_registry(), cache_set=failing_cache_set)
    assert service.deep_clean(url) == url.removesuffix("&utm_source=tracking")
    assert "Cleaner cache set failed (RuntimeError)" in caplog.text
    assert secret not in caplog.text
    assert "private.example" not in caplog.text
    assert "Could not cache" not in caplog.text
    assert caplog.records and all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("url", [
    "https://example.com/a%2Fb?token=a%26b%3Dc&return=%23section#part%3Ftwo",
    "https://example.com/?q=%25FF&next=https%3A%2F%2Fexample.net%2Fa%3Fx%3D1%26y%3D2",
    "https://example.com/%252Fitem?token=a%2526b",
    "https://example.com/a%2fb?token=%2f%2F%23%26",
    "https://example.com//a//b?token=abc?",
    "https://example.com/page#section?utm_source=fragment&x=1",
    "https://example.com/?q=one&q=two&flag&empty=#fragment?",
    "https://example.com/?q=%FF&escape=%broken",
])
def test_preserve_url_components_when_nothing_needs_cleaning(url: str) -> None:
    assert deep_clean(url) == url
    assert deep_clean(deep_clean(url)) == url


@pytest.mark.parametrize(("url", "expected"), [
    (
        "https://example.com/a%2Fb?token=a%26b%3Dc&utm_source=x#part%3Ftwo",
        "https://example.com/a%2Fb?token=a%26b%3Dc#part%3Ftwo",
    ),
    (
        "https://example.com//a//b?token=abc?&utm_source=x#fragment?",
        "https://example.com//a//b?token=abc?#fragment?",
    ),
    (
        "https://example.com/page?%75tm_source=x&q=one&q=two&flag&empty=#route?utm_source=y",
        "https://example.com/page?q=one&q=two&flag&empty=#route?utm_source=y",
    ),
    (
        "https://example.com/?hsCtaTracking=x&trkInfo=y&q=a%26b",
        "https://example.com/?q=a%26b",
    ),
])
def test_remove_tracking_without_reencoding_values(url: str, expected: str) -> None:
    assert deep_clean(url) == expected
    assert deep_clean(expected) == expected


def test_preprocess_converts_only_the_idn_hostname() -> None:
    url = "https://u:p@bücher.example:8443/a%2Fb?q=x%26y#z%23"
    assert preprocess(url) == "https://u:p@xn--bcher-kva.example:8443/a%2Fb?q=x%26y#z%23"
    ipv6 = "https://[2001:db8::1]:8443/a%2Fb?q=x%26y"
    assert preprocess(ipv6) == ipv6


@pytest.mark.parametrize(("url", "host"), [
    ("https://google.com:pw@example.org/url?q=test", "example.org"),
    ("https://example.org:pw@google.com/search?q=test", "google.com"),
    ("https://[2001:db8::1]:8443/a", "2001:db8::1"),
    ("https://twitter.com:443/search?q=test", "twitter.com"),
    ("https://twitter.com:invalid/search?q=test", ""),
    ("https://twitter.com:99999/search?q=test", ""),
])
def test_host_parser_respects_userinfo_ipv6_and_ports(url: str, host: str) -> None:
    assert CleanerUtils.extract_host(url) == host


@pytest.mark.parametrize("domain", [
    "twitter.com", "x.com", "instagram.com", "facebook.com", "reddit.com",
    "redd.it", "linkedin.com", "lnkd.in", "tiktok.com", "substack.com",
    "youtube.com", "youtu.be", "amazon.com", "github.com",
])
def test_domain_cleaners_preserve_unknown_parameters(domain: str) -> None:
    url = f"https://{domain}/page?custom_function=a%26b&utm_source=x#part"
    expected = f"https://{domain}/page?custom_function=a%26b#part"
    assert deep_clean(url) == expected


@pytest.mark.parametrize(("domain", "platform_key"), [
    ("kkinstagram.com", "igsh"),
    ("www.kkinstagram.com", "igsh"),
    ("facebookez.com", "mibextid"),
    ("www.facebookez.com", "mibextid"),
])
def test_retired_proxy_domains_receive_only_generic_cleaning(domain: str, platform_key: str) -> None:
    url = f"https://{domain}/post?{platform_key}=keep&utm_source=remove"
    expected = f"https://{domain}/post?{platform_key}=keep"
    assert [cleaner.id for cleaner in DEFAULT_REGISTRY.get_cleaners_for(url)] == ["general"]
    assert deep_clean(url) == expected
    assert deep_clean(expected) == expected


def test_custom_proxy_configuration_is_local_and_idempotent() -> None:
    registry = build_default_registry()
    untouched = build_default_registry()
    arguments = {"instagram": ("CUSTOM-IG.EXAMPLE", "custom-ig.example"),
                 "tiktok": ("custom-tt.example",)}
    registry.configure_proxy_domains(**arguments)
    registry.configure_proxy_domains(**arguments)
    service = CleanerService(registry)
    original_service = CleanerService(untouched)

    ig_url = "https://custom-ig.example/p/1?igsh=tracking&img_index=2&custom=a%26b&utm_source=x"
    ig_expected = "https://custom-ig.example/p/1?img_index=2&custom=a%26b"
    assert service.deep_clean(ig_url) == ig_expected
    assert service.deep_clean(ig_expected) == ig_expected
    assert original_service.deep_clean(ig_url) == ig_url.removesuffix("&utm_source=x")
    assert [c.id for c in DEFAULT_REGISTRY.get_cleaners_for(ig_url)] == ["general"]
    assert [c.id for c in registry.get_cleaners_for(ig_url)].count("instagram") == 1

    tt_url = "https://vm.custom-tt.example/id?_t=tracking&lang=en&custom=a%26b&utm_source=x"
    assert service.deep_clean(tt_url) == "https://vm.custom-tt.example/id?lang=en&custom=a%26b"
    assert original_service.deep_clean(tt_url) == tt_url.removesuffix("&utm_source=x")

    registry.configure_proxy_domains(instagram=("replacement.example",))
    assert service.deep_clean(ig_url) == ig_url.removesuffix("&utm_source=x")
    assert service.deep_clean(tt_url) == tt_url.removesuffix("&utm_source=x")
    assert service.deep_clean("https://replacement.example/p?igsh=tracking&custom=keep") == (
        "https://replacement.example/p?custom=keep"
    )


def test_builtin_proxy_registration_does_not_duplicate_cleaners() -> None:
    registry = build_default_registry()
    registry.configure_proxy_domains(instagram=("toinstagram.com",), tiktok=("tnktok.com",))
    assert [c.id for c in registry.get_cleaners_for("https://toinstagram.com/p?igsh=x")] == [
        "instagram", "general",
    ]


@pytest.mark.parametrize("configuration", [
    {"instagram": ("kkinstagram.com",)},
    {"tiktok": ("sub.facebookez.com",)},
    {"instagram": ("tiktok.com",)},
    {"tiktok": ("sub.toinstagram.com",)},
    {"instagram": ("custom.example",), "tiktok": ("sub.custom.example",)},
    {"instagram": ("https://custom.example",)},
    {"instagram": ("custom.example:443",)},
    {"instagram": ("custom.example/path",)},
])
def test_invalid_proxy_configuration_does_not_change_previous_aliases(configuration: dict) -> None:
    registry = build_default_registry()
    registry.configure_proxy_domains(instagram=("original.example",))
    with pytest.raises(ValueError):
        registry.configure_proxy_domains(**configuration)
    assert CleanerService(registry).deep_clean("https://original.example/p?igsh=x&custom=keep") == (
        "https://original.example/p?custom=keep"
    )


def test_x_search_retains_search_text() -> None:
    assert deep_clean("https://x.com/search?q=kotlin%20coroutines&s=20") == (
        "https://x.com/search?q=kotlin%20coroutines"
    )


@pytest.mark.parametrize("url", [
    "https://github.com/org/repo?tab=readme&utm_source=chat",
    "https://gist.github.com/user/id?tab=readme&utm_source=chat",
    "https://google.com/maps?tab=readme&utm_source=chat",
])
def test_general_cleaner_runs_for_mapped_and_fallback_domains(url: str) -> None:
    assert deep_clean(url) == url.removesuffix("&utm_source=chat")
    assert [cleaner.id for cleaner in DEFAULT_REGISTRY.get_cleaners_for(url)].count("general") == 1


@pytest.mark.parametrize(("url", "expected"), [
    ("https://facebook.com/post?ref=functional&utm_source=x",
     "https://facebook.com/post?ref=functional"),
    ("https://reddit.com/r/test?ref=functional&utm_source=x",
     "https://reddit.com/r/test?ref=functional"),
    ("https://music.youtube.com/watch?v=abc&si=functional&utm_source=x",
     "https://music.youtube.com/watch?v=abc&si=functional"),
    ("https://youtube.com/watch?v=abc&si=tracking&utm_source=x",
     "https://youtube.com/watch?v=abc"),
    ("https://facebook.com/post?%72ef=functional&utm_source=x",
     "https://facebook.com/post?%72ef=functional"),
])
def test_general_cleaner_respects_platform_functional_exceptions(url: str, expected: str) -> None:
    assert deep_clean(url) == expected


@pytest.mark.parametrize(("url", "expected"), [
    (
        "https://youtu.be/dQw4w9WgXcQ?index=2&list=PL123&custom=a%26b&si=x#t=42",
        "https://youtu.be/dQw4w9WgXcQ?index=2&list=PL123&custom=a%26b#t=42",
    ),
    (
        "https://youtube.com/results?search_query=https%3A%2F%2Fyoutu.be%2FdQw4w9WgXcQ",
        "https://youtube.com/results?search_query=https%3A%2F%2Fyoutu.be%2FdQw4w9WgXcQ",
    ),
    (
        "https://amazon.co.jp/name/dp/B08N5WRWNW?custom=a%26b&tag=x#reviews",
        "https://amazon.co.jp/dp/B08N5WRWNW?custom=a%26b#reviews",
    ),
    (
        "https://amazon.co.jp/s?k=https://amazon.com/dp/B08N5WRWNW&tag=x",
        "https://amazon.co.jp/s?k=https://amazon.com/dp/B08N5WRWNW",
    ),
    (
        "https://amazon.com/dp/B08N5WRWNWextra?custom=keep&tag=x",
        "https://amazon.com/dp/B08N5WRWNWextra?custom=keep",
    ),
])
def test_special_platform_routes_preserve_functional_components(url: str, expected: str) -> None:
    assert deep_clean(url) == expected


@pytest.mark.parametrize("host", ["google.com", "www.google.com", "www.google.co.jp"])
@pytest.mark.parametrize("key", ["q", "url", "%71"])
def test_google_wrapper_decodes_only_the_target_value_once(host: str, key: str) -> None:
    target = "https://example.org/a%2Fb?first=a%26b&second=%2523#part%3Ftwo"
    wrapper = f"https://{host}/url?{key}={quote(target, safe='')}&sa=D"
    assert deep_clean(wrapper) == target
    assert deep_clean(target) == target


def test_google_redirect_to_platform_preserves_its_functional_exceptions() -> None:
    target = "https://music.youtube.com/watch?v=abc&si=functional&utm_source=x"
    wrapper = "https://www.google.com/url?q=" + quote(target, safe="")
    assert deep_clean(wrapper) == "https://music.youtube.com/watch?v=abc&si=functional"


@pytest.mark.parametrize("url", [
    "https://evil.google.com/url?q=https://example.org",
    "https://www.google.com.example.org/url?q=https://example.org",
    "https://google.com:pw@example.org/url?q=https://example.org",
    "https://user:pw@google.com/url?q=https://example.org",
    "https://www.google.com/other/url?q=https://example.org",
    "https://www.google.com/url/extra?q=https://example.org",
    "https://www.google.com/urlfoo?q=https://example.org",
    "https://www.google.com/%75rl?q=https://example.org",
    "https://www.google.com/search?q=kotlin#/url?url=https://example.org",
    "https://www.google.com/search?q=kotlin&next=/url?url=https://example.org",
    "https://www.google.com/url#?q=https://example.org",
    "https://www.google.com/url?q=https://one.example&q=https://two.example",
    "https://www.google.com/url?q=https://one.example&%71=https://two.example",
    "https://www.google.com/url?url=https://one.example&q=https://two.example",
    "https://www.google.com/url?q=&q=https://example.org",
    "https://www.google.com/url?q",
    "https://www.google.com/url?q=",
    "https://www.google.com:99999/url?q=https://example.org",
    "https://www.google.com:bad/url?q=https://example.org",
    "https://www.google.com:8443/url?q=https://example.org",
    "http://www.google.com:443/url?q=https://example.org",
])
def test_non_wrappers_and_ambiguous_wrappers_are_not_unwrapped(url: str) -> None:
    assert GoogleSearchCleaner._extract_redirect(url) is None
    assert deep_clean(url) == url


@pytest.mark.parametrize("target", [
    "https://", "https:///missing-host", "https://example.org:bad",
    "https://example.org:99999", "https://example.org:",
    "https://user:pw@example.org/path", "https://exa mple.org/path",
    "https://example.org/line\nbreak", "https://example.org\\other/path",
    "https://example.org/%ZZ", "https://example.org/%", "https://[invalid]/path",
    "https://-invalid.example/path", "javascript:alert(1)", "file:///etc/passwd",
    "//example.org/path", "https%3A%2F%2Fexample.org",
])
def test_invalid_google_redirect_targets_remain_wrapped(target: str) -> None:
    wrapper = "https://www.google.com/url?q=" + quote(target, safe="")
    assert deep_clean(wrapper) == wrapper


@pytest.mark.parametrize("raw_target", ["https%3A%2F%2Fexample.org%FF", "https%3A%2F%2Fexample.org%ZZ"])
def test_google_target_decode_rejects_invalid_utf8_and_escapes(raw_target: str) -> None:
    wrapper = "https://www.google.com/url?q=" + raw_target
    assert deep_clean(wrapper) == wrapper
