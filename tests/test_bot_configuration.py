"""Configuration safety and cleaner/converter integration regressions."""
import asyncio

import pytest

import fixupxer_bot as bot


@pytest.mark.parametrize("domain", [
    "facebookez.com", "www.facebookez.com", "kkinstagram.com", "sub.kkinstagram.com",
    "instagram.com", "tiktok.com", "x.com", "github.com", "m.youtube.com",
    "tnktok.com", "https://custom.example", "custom.example:443", "user@custom.example",
    "127.0.0.1", "custom.example/path", "bad_label.example",
])
def test_invalid_retired_original_and_other_platform_proxies_are_ignored(domain):
    assert bot._parse_proxy_order(domain, bot._DEFAULT_IG_PROXIES, platform="instagram") == list(bot._DEFAULT_IG_PROXIES)


def test_proxy_configuration_normalizes_and_deduplicates():
    assert bot._parse_proxy_order(
        " CUSTOM.example.,custom.example,toinstagram.com ",
        bot._DEFAULT_IG_PROXIES, platform="instagram",
    ) == ["custom.example", "toinstagram.com"]


@pytest.mark.parametrize("domain", ["proxy.example", "sub.proxy.example", "example"])
def test_explicit_cross_platform_reservations_cannot_overlap(domain):
    assert bot._parse_proxy_order(
        domain, bot._DEFAULT_IG_PROXIES, reserved=("proxy.example",), platform="instagram",
    ) == list(bot._DEFAULT_IG_PROXIES)


@pytest.mark.parametrize("platform,url,expected", [
    ("instagram", "https://ig.custom.example/p/1?igsh=tracking&keep=a%26b", "https://ig.custom.example/p/1?keep=a%26b"),
    ("tiktok", "https://vm.tt.custom.example/a?utm_source=tracking&keep=a%23b", "https://vm.tt.custom.example/a?keep=a%23b"),
])
def test_custom_proxy_conversion_uses_its_domain_cleaner(monkeypatch, platform, url, expected):
    if platform == "instagram":
        monkeypatch.setattr(bot, "IG_PROXY_ORDER", ["ig.custom.example"])
        monkeypatch.setattr(bot, "_INSTAGRAM_HOSTS", ("instagram.com", "ig.custom.example"))
    else:
        monkeypatch.setattr(bot, "TIKTOK_PROXY_ORDER", ["tt.custom.example"])
        monkeypatch.setattr(bot, "_TIKTOK_HOSTS", ("tiktok.com", "tt.custom.example"))
    bot.cleaner_engine.DEFAULT_REGISTRY.configure_proxy_domains(
        instagram=bot.IG_PROXY_ORDER, tiktok=bot.TIKTOK_PROXY_ORDER,
    )
    result = asyncio.run(bot.convert_supported_url(url))
    assert result == (platform, expected, None)


@pytest.mark.parametrize("url, expected", [
    ("https://facebook.com/watch?v=123&fbclid=tracking&custom=kept", "https://facebook.com/watch?v=123&custom=kept"),
    ("https://kkinstagram.com/p/1?igsh=kept&utm_source=gone", "https://kkinstagram.com/p/1?igsh=kept"),
    ("https://facebookez.com/post?fbclid=gone&custom=kept", "https://facebookez.com/post?custom=kept"),
])
def test_facebook_and_retired_domains_never_redirect(url, expected):
    _, fixed, clean = asyncio.run(bot.convert_supported_url(url))
    assert fixed == expected
    assert clean is None


@pytest.mark.parametrize("url", [
    "https://x.com:pw@example.org/status/123?s=20",
    "https://x.com:invalid/status/123?s=20",
    "https://x.com:65536/status/123?s=20",
    "https://x.com/status/123?token=bad%xx",
    "https://x.com/status/123\n?s=20",
    "file:///tmp/file",
])
def test_ambiguous_or_malformed_urls_do_not_trigger_reposts(url):
    assert asyncio.run(bot.convert_supported_url(url)) == (None, None, None)


def test_non_default_port_is_preserved_without_proxy_rewrite():
    assert asyncio.run(bot.convert_supported_url("https://x.com:8443/search?q=a%26b&s=20")) == (
        bot.PLATFORM_OTHER, "https://x.com:8443/search?q=a%26b", None,
    )


def test_explicit_default_port_can_still_convert():
    platform, fixed, _ = asyncio.run(bot.convert_supported_url("https://x.com:443/u/status/1?s=20"))
    assert platform == bot.PLATFORM_X
    assert fixed == "https://fixupx.com/u/status/1"
