"""Unit tests for the bot's URL helpers and message builder."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Disable embed verification so tests don't open sockets.
os.environ.setdefault("FIXUPXER_IG_VERIFY_EMBED", "0")

import fixupxer_bot as bot  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---- _identify_platform ------------------------------------------------------

@pytest.mark.parametrize(
    "domain, expected",
    [
        ("x.com", bot.PLATFORM_X),
        ("twitter.com", bot.PLATFORM_X),
        ("vxtwitter.com", bot.PLATFORM_X),
        ("mobile.twitter.com", bot.PLATFORM_X),
        ("instagram.com", bot.PLATFORM_INSTAGRAM),
        ("eeinstagram.com", bot.PLATFORM_INSTAGRAM),
        ("facebook.com", bot.PLATFORM_FACEBOOK),
        ("fb.com", bot.PLATFORM_FACEBOOK),
        ("fb.watch", bot.PLATFORM_FACEBOOK),
        ("m.facebook.com", bot.PLATFORM_FACEBOOK),
        ("tiktok.com", bot.PLATFORM_TIKTOK),
        ("vm.tiktok.com", bot.PLATFORM_TIKTOK),
        ("tnktok.com", bot.PLATFORM_TIKTOK),
        ("kktiktok.com", bot.PLATFORM_TIKTOK),
        ("vxtiktok.com", bot.PLATFORM_TIKTOK),
        # Substring false-positives must NOT match.
        ("maxx.com", None),
        ("fakeinstagram.scam.com", None),
        ("twitter.com.evil.example", None),
        ("youtube.com", None),  # YT is intentionally not a converter target.
    ],
)
def test_identify_platform(domain: str, expected) -> None:
    assert bot._identify_platform(domain) == expected


# ---- _trim_url_trail ---------------------------------------------------------

def test_trim_url_trail_preserves_balanced_parens() -> None:
    url = "https://en.wikipedia.org/wiki/Foo_(bar)"
    assert bot._trim_url_trail(url) == url


def test_trim_url_trail_strips_punctuation() -> None:
    assert bot._trim_url_trail("https://x.com/foo!?,.") == "https://x.com/foo"
    assert bot._trim_url_trail("https://x.com/foo).") == "https://x.com/foo"


# ---- convert_supported_url ---------------------------------------------------

def test_convert_x_keeps_lang() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://x.com/u/status/123?s=20&t=abc&lang=en",
    ))
    assert p == bot.PLATFORM_X
    assert "fixupx.com" in fixed
    assert "lang=en" in fixed
    assert "s=20" not in fixed


def test_convert_facebook_keeps_set_and_notif_id() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.facebook.com/photo.php?fbid=1&set=pcb.2&notif_id=3&fbclid=4",
    ))
    assert p == bot.PLATFORM_FACEBOOK
    assert "set=pcb.2" in fixed
    assert "notif_id=3" in fixed
    assert "fbclid" not in fixed


def test_convert_vxtwitter_does_not_rewrite_domain() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://vxtwitter.com/elonmusk/status/123?s=20",
    ))
    assert p == bot.PLATFORM_X
    assert "vxtwitter.com" in fixed
    assert "s=20" not in fixed


def test_convert_instagram_uses_first_proxy_when_verify_off() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.instagram.com/p/ABC/?igsh=spam&img_index=2",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    assert "img_index=2" in fixed
    assert "igsh" not in fixed
    # Default first proxy is the first entry of _DEFAULT_IG_PROXIES.
    assert bot._DEFAULT_IG_PROXIES[0] in fixed


def test_convert_instagram_rewrites_historical_proxy() -> None:
    """A URL on a dead historical proxy gets re-hosted onto an active one."""
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.eeinstagram.com/p/ABC/?igsh=spam",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    assert "eeinstagram.com" not in fixed
    assert "igsh" not in fixed
    assert bot._DEFAULT_IG_PROXIES[0] in fixed


def test_convert_instagram_strips_www_from_proxy_paste() -> None:
    """A pasted www.<active-proxy> URL gets normalised to the bare host
    (we always emit bare-host proxy URLs, regardless of which proxy)."""
    proxy = bot._DEFAULT_IG_PROXIES[0]
    p, fixed, clean = _run(bot.convert_supported_url(
        f"https://www.{proxy}/p/ABC/?igsh=spam",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    assert f"://{proxy}/" in fixed
    assert f"www.{proxy}" not in fixed
    assert "igsh" not in fixed


def test_convert_instagram_emits_bare_host_for_default_proxy() -> None:
    """Newly converted IG URLs (from instagram.com input) use bare host too."""
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.instagram.com/p/ABC/?igsh=spam",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    proxy = bot._DEFAULT_IG_PROXIES[0]
    assert f"://{proxy}/" in fixed
    assert f"www.{proxy}" not in fixed


def test_convert_tiktok_rewrites_and_preserves_subdomain() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.tiktok.com/@user/video/123?_r=1&lang=en",
    ))
    assert p == bot.PLATFORM_TIKTOK
    assert "www.tnktok.com" in fixed
    assert "lang=en" in fixed
    assert "_r=1" not in fixed
    assert clean is not None and "tiktok.com" in clean


def test_convert_tiktok_short_link_keeps_vm_prefix() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://vm.tiktok.com/ZMabcdef/",
    ))
    assert p == bot.PLATFORM_TIKTOK
    assert fixed == "https://vm.tnktok.com/ZMabcdef/"
    assert clean == "https://vm.tiktok.com/ZMabcdef/"


def test_convert_tiktok_migrates_legacy_proxy() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://vxtiktok.com/@user/video/123",
    ))
    assert p == bot.PLATFORM_TIKTOK
    assert "tnktok.com" in fixed
    # Fallback link must point at tiktok.com, not the dead legacy proxy.
    assert clean == "https://tiktok.com/@user/video/123"


def test_convert_tiktok_already_on_proxy_cleans_only() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://tnktok.com/@user/video/123?_r=1",
    ))
    assert p == bot.PLATFORM_TIKTOK
    assert "tnktok.com" in fixed
    assert "_r=1" not in fixed
    assert clean is None


def test_convert_tiktok_already_clean_on_proxy_is_noop() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://tnktok.com/@user/video/123",
    ))
    assert (p, fixed, clean) == (None, None, None)


def test_tiktok_prefers_healthy_proxy(monkeypatch) -> None:
    """When the first TikTok proxy fails its probe, the next healthy one is
    used — with the subdomain prefix preserved on the probed host."""
    first, second = bot.TIKTOK_PROXY_ORDER[0], bot.TIKTOK_PROXY_ORDER[1]
    probed_hosts: list[str] = []

    async def fake_probe(proxy, path, host=None):
        probed_hosts.append(host or proxy)
        if proxy == first:
            return False, None, None
        return True, "og-url", f"https://{host or proxy}{path}"

    monkeypatch.setattr(bot, "TIKTOK_VERIFY_EMBED", True)
    monkeypatch.setattr(bot, "_tt_probe", fake_probe)
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.tiktok.com/@user/video/123",
    ))
    assert p == bot.PLATFORM_TIKTOK
    assert f"www.{second}" in fixed
    assert probed_hosts == [f"www.{first}", f"www.{second}"]


def test_tiktok_all_fail_returns_none_fixed(monkeypatch) -> None:
    async def fake_probe(proxy, path, host=None):
        return False, None, None

    monkeypatch.setattr(bot, "TIKTOK_VERIFY_EMBED", True)
    monkeypatch.setattr(bot, "_tt_probe", fake_probe)
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.tiktok.com/@user/video/123",
    ))
    assert p == bot.PLATFORM_TIKTOK
    assert fixed is None
    assert clean == "https://www.tiktok.com/@user/video/123"


# ---- Probe video validation ---------------------------------------------------

_ADAMLIKES_STYLE_HTML = """
<meta name="twitter:player:stream" content="/videos/ABC/1"/>
<meta property="og:video" content="/videos/ABC/1"/>
<meta property="og:image" content="/images/ABC/1"/>
"""

_PHOTO_ONLY_HTML = '<meta property="og:image" content="/images/ABC/1"/>'


def test_og_video_url_extracted_and_photo_pages_return_none() -> None:
    assert bot._og_video_url(_ADAMLIKES_STYLE_HTML) == "/videos/ABC/1"
    assert bot._og_video_url(_PHOTO_ONLY_HTML) is None


class _FakeStream:
    def __init__(self, status_code: int, content_type: str) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, status_code: int, content_type: str) -> None:
        self._resp = (status_code, content_type)

    def stream(self, method: str, url: str, **kwargs):
        return _FakeStream(*self._resp)


def test_media_is_video_rejects_jpeg_and_errors_accepts_mp4() -> None:
    # adamlikes.men failure mode: og:video endpoint 302s to a JPEG cover frame.
    assert asyncio.run(
        bot._media_is_video(_FakeClient(200, "image/jpeg"), "https://p/v/1")
    ) is False
    assert asyncio.run(
        bot._media_is_video(_FakeClient(500, "text/plain"), "https://p/v/1")
    ) is False
    assert asyncio.run(
        bot._media_is_video(_FakeClient(200, "video/mp4"), "https://p/v/1")
    ) is True


# ---- Instagram proxy selection (probe mocked) --------------------------------

def test_ig_prefers_direct_serving_proxy_over_redirect(monkeypatch) -> None:
    """A proxy that 302s back to instagram.com must lose to one that serves
    the embed itself (plain instagram.com links don't embed in Telegram)."""
    first, second = bot.IG_PROXY_ORDER[0], bot.IG_PROXY_ORDER[1]

    async def fake_probe(proxy, path):
        if proxy == first:
            return True, "og-url", f"https://www.instagram.com{path}"
        return True, "og-url", f"https://{proxy}{path}"

    monkeypatch.setattr(bot, "IG_VERIFY_EMBED", True)
    monkeypatch.setattr(bot, "_ig_probe", fake_probe)
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.instagram.com/reel/ABC/?igsh=spam",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    assert f"://{second}/" in fixed
    assert clean == "https://www.instagram.com/reel/ABC/"


def test_ig_redirect_target_used_when_no_proxy_serves_directly(monkeypatch) -> None:
    async def fake_probe(proxy, path):
        return True, "og-url", f"https://www.instagram.com{path}"

    monkeypatch.setattr(bot, "IG_VERIFY_EMBED", True)
    monkeypatch.setattr(bot, "_ig_probe", fake_probe)
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://www.instagram.com/reel/ABC/?igsh=spam",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    assert fixed == "https://www.instagram.com/reel/ABC/"


def test_unsupported_clean_url_returns_none() -> None:
    """An already-clean non-platform URL must not trigger a bot reply."""
    p, fixed, clean = _run(bot.convert_supported_url("https://example.com/page"))
    assert (p, fixed, clean) == (None, None, None)


def test_youtube_short_link_is_cleaned_as_other() -> None:
    """YouTube links are cleaned (PLATFORM_OTHER), domain left untouched."""
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://youtu.be/reWsf4QU054?si=OiqYglSsbfbcXD33",
    ))
    assert p == bot.PLATFORM_OTHER
    assert "si=" not in fixed
    assert "youtu.be" in fixed
    assert clean is None  # 2-link layout


def test_generic_url_with_utm_is_cleaned_as_other() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://example.com/article?utm_source=newsletter&utm_medium=email&id=1",
    ))
    assert p == bot.PLATFORM_OTHER
    assert "utm_source" not in fixed
    assert "utm_medium" not in fixed
    assert "id=1" in fixed
    assert clean is None


def test_already_on_fixupx_returns_none_when_clean() -> None:
    """A clean fixupx URL is a no-op; bot must not reply."""
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://fixupx.com/u/status/123",
    ))
    assert (p, fixed, clean) == (None, None, None)


def test_already_on_fixupx_with_tracking_returns_x_with_clean_none() -> None:
    p, fixed, clean = _run(bot.convert_supported_url(
        "https://fixupx.com/u/status/123?s=20",
    ))
    assert p == bot.PLATFORM_X
    assert "fixupx.com" in fixed
    assert "s=20" not in fixed
    assert clean is None  # already on proxy → no fallback link


# ---- _build_message ----------------------------------------------------------

def test_build_message_escapes_special_chars() -> None:
    msg = bot._build_message(
        platform=bot.PLATFORM_X,
        username="@user_with_dot.",
        fixed_url="https://fixupx.com/u/status/123",
        clean_url="https://x.com/u/status/123",
        original_url="https://x.com/u/status/123?s=20",
        user_text="Check (this) out!",
    )
    # Escaped MarkdownV2 dot in username + escaped exclamation/parens in user text.
    assert r"\." in msg
    assert r"\(this\)" in msg
    assert r"\!" in msg


def test_build_message_includes_all_three_links_when_clean_provided() -> None:
    msg = bot._build_message(
        platform=bot.PLATFORM_INSTAGRAM,
        username="@a",
        fixed_url="https://toinstagram.com/p/ABC/",
        clean_url="https://www.instagram.com/p/ABC/",
        original_url="https://www.instagram.com/p/ABC/?igsh=spam",
        user_text="",
    )
    # MarkdownV2 escapes "&" → "\&"; check a substring that survives escaping.
    assert "Cleaned" in msg and "converted URL" in msg
    assert "Clean URL" in msg
    assert "Original" in msg


def test_build_message_escapes_paren_in_urls() -> None:
    """URLs containing ')' must be escaped inside MarkdownV2 inline links,
    otherwise Telegram rejects the whole message with BadRequest."""
    msg = bot._build_message(
        platform=bot.PLATFORM_OTHER,
        username="@a",
        fixed_url="https://en.wikipedia.org/wiki/Foo_(bar)",
        clean_url=None,
        original_url="https://en.wikipedia.org/wiki/Foo_(bar)?utm_source=x",
        user_text="",
    )
    assert "(https://en.wikipedia.org/wiki/Foo_(bar\\))" in msg


def test_build_message_two_link_layout_when_clean_url_none() -> None:
    """When clean_url is None (PLATFORM_OTHER or already-on-proxy) drop fallback link."""
    msg = bot._build_message(
        platform=bot.PLATFORM_OTHER,
        username="@a",
        fixed_url="https://youtu.be/abc",
        clean_url=None,
        original_url="https://youtu.be/abc?si=xyz",
        user_text="",
    )
    assert "✅ Cleaned URL" in msg
    # No "& converted" suffix and no "if embed isn't available" row.
    assert "& converted" not in msg
    assert "if embed isn" not in msg
    assert "Original" in msg
