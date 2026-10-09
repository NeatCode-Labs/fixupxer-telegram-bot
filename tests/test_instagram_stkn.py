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


def test_reported_instagram_exln_reel_is_cleaned_and_converted(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = "https://www.instagram.com/reel/DeQMt21oZ9Y/?exln=MWQ2dWVhcm1pYndsag=="
    clean = "https://www.instagram.com/reel/DeQMt21oZ9Y/"
    assert deep_clean(url) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/reel/DeQMt21oZ9Y/",
        clean,
    )


def test_reported_instagram_obrf_reel_is_cleaned_and_converted(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = "https://www.instagram.com/reel/DeO0lB3ub9j/?obrf=MWozZ3k1aGgyYzlnMQ=="
    clean = "https://www.instagram.com/reel/DeO0lB3ub9j/"
    assert deep_clean(url) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/reel/DeO0lB3ub9j/",
        clean,
    )


def test_reported_instagram_vrfl_reel_is_cleaned_and_converted(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = "https://www.instagram.com/reel/Dd_BUoKTr-N/?vrfl=MXVyMTZhZnU4OWNjMA=="
    clean = "https://www.instagram.com/reel/Dd_BUoKTr-N/"
    assert deep_clean(url) == clean
    assert deep_clean(clean) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/reel/Dd_BUoKTr-N/",
        clean,
    )


def test_instagram_canonical_reel_drops_unknown_params_and_keeps_carousel_selector(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = (
        "https://www.instagram.com/reel/Synthetic/?exln=MWQ2dWVhcm1pYndsag=="
        "&obrf=MWozZ3k1aGgyYzlnMQ==&vrfl=MXVyMTZhZnU4OWNjMA=="
        "&img_index=0002&story_media_id=456&custom=a%26b%3Dc&custom=two#slide"
    )
    clean = "https://www.instagram.com/reel/Synthetic/?img_index=2"
    fixed = f"https://{bot.IG_PROXY_ORDER[0]}/reel/Synthetic/?img_index=2"

    assert deep_clean(url) == clean
    assert deep_clean(clean) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        fixed,
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


def test_existing_instagram_ig_rid_keeps_carousel_selector_on_canonical_post(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    url = (
        "https://www.instagram.com/p/Synthetic/?ig_rid=tracking"
        "&img_index=2&custom=a%26b%3Dc&custom=two"
    )
    clean = "https://www.instagram.com/p/Synthetic/?img_index=2"
    assert deep_clean(url) == clean
    assert deep_clean(clean) == clean
    assert asyncio.run(bot.convert_supported_url(url)) == (
        bot.PLATFORM_INSTAGRAM,
        f"https://{bot.IG_PROXY_ORDER[0]}/p/Synthetic/?img_index=2",
        clean,
    )


@pytest.mark.parametrize("host", [
    "instagram.com", "www.instagram.com", "m.instagram.com", "WWW.Instagram.com",
    "toinstagram.com", "adamlikes.men", "instagram7.com",
    "eeinstagram.com", "ddinstagram.com", "www.toinstagram.com",
])
def test_instagram_origin_permalink_and_proxy_hosts_keep_distinct_query_policies(host):
    base = f"https://{host}/p/Synthetic/"
    kept = "img_index=2&story_media_id=123&custom=a%26b%3Dc&custom=two&flag&empty="
    source = (
        f"{base}?stkn=tracking&igsi=tracking&ig_rid=tracking"
        f"&exln=MWQ2dWVhcm1pYndsag==&obrf=MWozZ3k1aGgyYzlnMQ==&{kept}"
        "#part?stkn=fragment&exln=fragment&obrf=fragment"
    )
    if host.lower() in {"instagram.com", "www.instagram.com", "m.instagram.com"}:
        expected = f"{base}?img_index=2"
    else:
        expected = f"{base}?{kept}#part?stkn=fragment&exln=fragment&obrf=fragment"
    assert deep_clean(source) == expected
    assert deep_clean(expected) == expected


def test_instagram_proxy_gallery_path_and_functional_query_are_preserved():
    proxy = bot.IG_PROXY_ORDER[0]
    base = f"https://{proxy}/p/Synthetic/photo/2"
    url = f"{base}?exln=tracking&img_index=2&custom=a%26b#slide"
    expected = f"{base}?img_index=2&custom=a%26b#slide"
    assert deep_clean(url) == expected
    assert deep_clean(expected) == expected


@pytest.mark.parametrize("host", ["instagram.com", "www.instagram.com", "m.instagram.com"])
def test_instagram_canonical_origin_accepts_only_http_default_authorities(host):
    expected_http = f"http://{host}:80/reel/Synthetic/?img_index=2"
    assert deep_clean(
        f"http://{host}:80/reel/Synthetic/?vrfl=future&img_index=0002#fragment"
    ) == expected_http
    expected_https = f"https://{host}:443/p/Synthetic/"
    assert deep_clean(
        f"https://{host}:443/p/Synthetic/?vrfl=future#fragment"
    ) == expected_https


@pytest.mark.parametrize("path", [
    "/user.name_1/p/Synthetic/", "/user_name/reels/Synthetic/", "/tv/Synthetic",
])
def test_instagram_canonical_permalink_routes_accept_user_prefix_and_content_types(path):
    base = f"https://www.instagram.com{path}"
    assert deep_clean(f"{base}?vrfl=future&img_index=2&custom=x#fragment") == (
        f"{base}?img_index=2"
    )


@pytest.mark.parametrize(("url", "expected"), [
    (
        "https://www.instagram.com/reel/Synthetic/?vrfl=future&img_index=0002&custom=x#part",
        "https://www.instagram.com/reel/Synthetic/?img_index=2",
    ),
    (
        "https://instagram.com/p/Synthetic/?img_index=2&img_index=02&vrfl=future",
        "https://instagram.com/p/Synthetic/?img_index=2",
    ),
    (
        "https://instagram.com/p/Synthetic/?img_index=00000000000000000002",
        "https://instagram.com/p/Synthetic/?img_index=2",
    ),
    ("https://instagram.com/reel/Synthetic/?img_index=2&img_index=3", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?img_index=0", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?img_index=2147483648", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?img_index=+2", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?img_index=2.0", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?img_index=2&img_index=", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?img_index=%32", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?%69mg_index=2", "https://instagram.com/reel/Synthetic/"),
    ("https://instagram.com/reel/Synthetic/?IMG_INDEX=2", "https://instagram.com/reel/Synthetic/"),
])
def test_instagram_canonical_post_keeps_only_one_unambiguous_positive_img_index(url, expected):
    assert deep_clean(url) == expected
    assert deep_clean(expected) == expected


@pytest.mark.parametrize("path", [
    "/stories/Synthetic/123/", "/share/reel/Synthetic/", "/accounts/login/",
    "/accounts/reel/Synthetic/", "/oauth/authorize/", "/oauth/reel/Synthetic/",
    "/explore/tags/example/", "/explore/reel/Synthetic/", "/direct/inbox/",
    "/direct/reel/Synthetic/", "/login/", "/Stories/reel/Synthetic/",
    "/oembed/", "/p/Synthetic/photo/2", "/./reel/Synthetic/", "/../reel/Synthetic/",
])
def test_instagram_special_or_noncanonical_paths_keep_unknown_query_and_fragment(path):
    base = f"https://www.instagram.com{path}"
    source = (
        f"{base}?exln=tracking&vrfl=future&custom=a%26b&img_index=2"
        "&story_media_id=456#fragment"
    )
    expected = f"{base}?vrfl=future&custom=a%26b&img_index=2&story_media_id=456#fragment"
    assert deep_clean(source) == expected
    assert deep_clean(expected) == expected


@pytest.mark.parametrize(("url", "expected"), [
    (
        "https://user@instagram.com/reel/Synthetic/?stkn=tracking&vrfl=future&custom=x#fragment",
        "https://user@instagram.com/reel/Synthetic/?vrfl=future&custom=x#fragment",
    ),
    (
        "https://instagram.com:8443/reel/Synthetic/?stkn=tracking&vrfl=future&custom=x#fragment",
        "https://instagram.com:8443/reel/Synthetic/?vrfl=future&custom=x#fragment",
    ),
    (
        "https://sub.instagram.com/reel/Synthetic/?stkn=tracking&vrfl=future&custom=x#fragment",
        "https://sub.instagram.com/reel/Synthetic/?vrfl=future&custom=x#fragment",
    ),
    (
        "https://instagram.com:bad/reel/Synthetic/?vrfl=future&custom=x#fragment",
        "https://instagram.com:bad/reel/Synthetic/?vrfl=future&custom=x#fragment",
    ),
    (
        "https://instagram.com:/reel/Synthetic/?vrfl=future&custom=x#fragment",
        "https://instagram.com:/reel/Synthetic/?vrfl=future&custom=x#fragment",
    ),
    (
        "https://www.instagram.com/reel/Synthetic/?stkn=tracking&custom=%ZZ#fragment",
        "https://www.instagram.com/reel/Synthetic/?custom=%ZZ#fragment",
    ),
    (
        "https://instagram.com.example.org/reel/Synthetic/?vrfl=future&custom=x#fragment",
        "https://instagram.com.example.org/reel/Synthetic/?vrfl=future&custom=x#fragment",
    ),
])
def test_instagram_canonical_policy_rejects_unsafe_authorities_and_malformed_urls(url, expected):
    assert deep_clean(url) == expected


def test_instagram_share_keys_duplicates_and_encoding_keep_exact_key_policy():
    base = "https://instagram.com/stories/Synthetic/"
    # Existing platform keys are case-sensitive and percent-decoded only once.
    kept = (
        "STKN=upper&Stkn=mixed&%53TKN=encoded_upper&%2573tkn=double"
        "&stkn_extra=keep&xstkn=keep&custom=stkn%3Dvalue%26next%3D2"
        "&IGSI=upper&%2569gsi=double&igsi_extra=keep"
        "&IG_RID=upper&%2569g_rid=double&ig_rid_extra=keep"
        "&EXLN=upper&Exln=mixed&%45XLN=encoded_upper&%2565xln=double"
        "&exln_extra=keep&xexln=keep"
        "&OBRF=upper&Obrf=mixed&%4FBRF=encoded_upper&%256Fbrf=double"
        "&obrf_extra=keep&xobrf=keep"
    )
    url = (
        f"{base}?stkn=one&{kept}&stkn=two&stkn=&stkn&%73tkn=three&st%6Bn=four"
        "&igsi=one&igsi=two&igsi=&igsi&%69gsi=three"
        "&ig_rid=one&ig_rid=two&ig_rid=&ig_rid&ig%5Frid=three"
        "&exln=one&exln=two&exln=&exln&%65xln=three&ex%6Cn=four"
        "&obrf=one&obrf=two&obrf=&obrf&%6Fbrf=three&ob%72f=four"
    )
    expected = f"{base}?{kept}"
    assert deep_clean(url) == expected
    assert deep_clean(expected) == expected


@pytest.mark.parametrize("url", [
    "https://instagram.com/stories/Synthetic/#?stkn=fragment&igsi=fragment&ig_rid=fragment&exln=fragment&obrf=fragment",
    "https://instagram.com/stories/Synthetic/?stkn%ZZ=keep&%FFstkn=keep&exln%ZZ=keep&%FFobrf=keep",
])
def test_instagram_share_keys_fragment_and_malformed_keys_are_unchanged(url):
    assert deep_clean(url) == url


@pytest.mark.parametrize("host", [
    "instagram.com.example.org", "notinstagram.com", "example.org/instagram.com",
    "instagram.com@example.org", "toinstagram.com.example.org",
    "kkinstagram.com", "www.kkinstagram.com", "tiktok.com", "example.org",
])
def test_instagram_share_keys_do_not_expand_to_other_hosts(host):
    expected = (
        f"https://{host}/reel/Synthetic/?stkn=keep&igsi=keep&ig_rid=keep"
        "&exln=keep&obrf=keep&custom=a%26b"
    )
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
        "?%73tkn=tracking&igsi=tracking&ig_rid=tracking"
        "&%65xln=tracking&%6Fbrf=tracking&img_index=2&custom=a%26b"
    )
    expected = "https://ig.custom.example/reel/Synthetic/?img_index=2&custom=a%26b"
    assert asyncio.run(bot.convert_supported_url(url)) == (bot.PLATFORM_INSTAGRAM, expected, None)
    assert asyncio.run(bot.convert_supported_url(expected)) == (None, None, None)
    # Registering a custom Instagram alias does not change independent registries.
    assert CleanerService(build_default_registry()).deep_clean(url) == url
