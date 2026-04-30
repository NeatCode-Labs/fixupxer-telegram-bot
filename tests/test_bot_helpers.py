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
        "https://www.kkinstagram.com/p/ABC/?igsh=spam",
    ))
    assert p == bot.PLATFORM_INSTAGRAM
    assert "kkinstagram.com" not in fixed
    assert "igsh" not in fixed
    assert bot._DEFAULT_IG_PROXIES[0] in fixed


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
        fixed_url="https://www.toinstagram.com/p/ABC/",
        clean_url="https://www.instagram.com/p/ABC/",
        original_url="https://www.instagram.com/p/ABC/?igsh=spam",
        user_text="",
    )
    # MarkdownV2 escapes "&" → "\&"; check a substring that survives escaping.
    assert "Cleaned" in msg and "converted URL" in msg
    assert "Clean URL" in msg
    assert "Original" in msg


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
