"""Instagram share-token removal without widening query or host matching."""
from __future__ import annotations

import asyncio

import pytest

import fixupxer_bot as bot
from cleaners import CleanerService, deep_clean
from cleaners.impl import build_default_registry


def test_reported_instagram_stkn_reel_is_cleaned_and_converted(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = "https://www.instagram.com/reel/Dc4fAOCs97R/?stkn=anBpYnlkeG82MDJz"
    clean = "https://www.instagram.com/reel/Dc4fAOCs97R/"
    assert deep_clean(url) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/reel/Dc4fAOCs97R/",
        clean,
    )


def test_previous_instagram_igsi_reel_is_cleaned_and_converted(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = "https://www.instagram.com/reel/Da0a2ylvv4z/?igsi=Nm44MGppNTFIZXNw"
    clean = "https://www.instagram.com/reel/Da0a2ylvv4z/"
    assert deep_clean(url) == clean
    assert deep_clean(clean) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/reel/Da0a2ylvv4z/",
        clean,
    )


def test_existing_instagram_ig_rid_preserves_carousel_and_unknown_values(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = (
        "https://www.instagram.com/p/Synthetic/?ig_rid=tracking"
        "&img_index=2&custom=a%26b%3Dc&custom=two"
    )
    clean = "https://www.instagram.com/p/Synthetic/?img_index=2&custom=a%26b%3Dc&custom=two"
    assert deep_clean(url) == clean
    assert deep_clean(clean) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/p/Synthetic/?img_index=2&custom=a%26b%3Dc&custom=two",
        clean,
    )


@pytest.mark.parametrize("host", [
    "instagram.com", "www.instagram.com", "m.instagram.com", "WWW.Instagram.com",
    "toinstagram.com", "adamlikes.men", "instagram7.com",
    "eeinstagram.com", "ddinstagram.com", "www.toinstagram.com",
])
def test_instagram_share_keys_on_supported_hosts_preserve_functional_query(host):
    base = f"https://{host}/p/Synthetic/"
    kept = "img_index=2&story_media_id=123&custom=a%26b%3Dc&custom=two&flag&empty="
    expected = f"{base}?{kept}#part?stkn=fragment"
    assert deep_clean(
        f"{base}?stkn=tracking&igsi=tracking&ig_rid=tracking&{kept}#part?stkn=fragment"
    ) == expected
    assert deep_clean(expected) == expected


def test_instagram_share_keys_duplicates_and_encoding_keep_exact_key_policy():
    base = "https://instagram.com/reel/Synthetic/"
    # Existing platform keys are case-sensitive and percent-decoded only once.
    kept = (
        "STKN=upper&Stkn=mixed&%53TKN=encoded_upper&%2573tkn=double"
        "&stkn_extra=keep&xstkn=keep&custom=stkn%3Dvalue%26next%3D2"
        "&IGSI=upper&%2569gsi=double&igsi_extra=keep"
        "&IG_RID=upper&%2569g_rid=double&ig_rid_extra=keep"
    )
    url = (
        f"{base}?stkn=one&{kept}&stkn=two&stkn=&stkn&%73tkn=three&st%6Bn=four"
        "&igsi=one&igsi=two&igsi=&igsi&%69gsi=three"
        "&ig_rid=one&ig_rid=two&ig_rid=&ig_rid&ig%5Frid=three"
    )
    expected = f"{base}?{kept}"
    assert deep_clean(url) == expected
    assert deep_clean(expected) == expected


@pytest.mark.parametrize("url", [
    "https://instagram.com/reel/Synthetic/#?stkn=fragment&igsi=fragment&ig_rid=fragment",
    "https://instagram.com/reel/Synthetic/?stkn%ZZ=keep&%FFstkn=keep",
])
def test_instagram_share_keys_fragment_and_malformed_keys_are_unchanged(url):
    assert deep_clean(url) == url


@pytest.mark.parametrize("host", [
    "instagram.com.example.org", "notinstagram.com", "example.org/instagram.com",
    "instagram.com@example.org", "toinstagram.com.example.org",
    "kkinstagram.com", "www.kkinstagram.com", "tiktok.com", "example.org",
])
def test_instagram_share_keys_do_not_expand_to_other_hosts(host):
    expected = f"https://{host}/reel/Synthetic/?stkn=keep&igsi=keep&ig_rid=keep&custom=a%26b"
    assert deep_clean(expected + "&utm_source=remove") == expected
    assert deep_clean(expected) == expected


def test_instagram_share_keys_custom_proxy_uses_local_alias_and_bot_conversion(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    monkeypatch.setattr(bot, "IG_PROXY_ORDER", ["ig.custom.example"])
    monkeypatch.setattr(bot, "_INSTAGRAM_HOSTS", ("instagram.com", "ig.custom.example"))
    bot.cleaner_engine.DEFAULT_REGISTRY.configure_proxy_domains(
        instagram=bot.IG_PROXY_ORDER, tiktok=bot.TIKTOK_PROXY_ORDER,
    )
    url = (
        "https://ig.custom.example/reel/Synthetic/"
        "?%73tkn=tracking&igsi=tracking&ig_rid=tracking&img_index=2&custom=a%26b"
    )
    expected = "https://ig.custom.example/reel/Synthetic/?img_index=2&custom=a%26b"
    assert asyncio.run(bot.convert_supported_url(url)) == (bot.PLATFORM_INSTAGRAM, expected, None)
    assert asyncio.run(bot.convert_supported_url(expected)) == (None, None, None)
    # Registering a custom Instagram alias does not change independent registries.
    assert CleanerService(build_default_registry()).deep_clean(url) == url
