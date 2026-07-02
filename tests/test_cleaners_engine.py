"""Engine-level regression tests: host matching and URL rebuilding."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleaners import deep_clean  # noqa: E402
from cleaners.base import CleanerUtils  # noqa: E402


def test_domain_in_path_does_not_trigger_cleaner() -> None:
    """'x.com' as path text must not activate the aggressive Twitter cleaner."""
    url = "https://news.example.com/story-about-x.com?id=5"
    assert deep_clean(url) == url


def test_host_substring_false_positive_not_matched() -> None:
    """'t.me' appears inside 'about.meta.com'; the Telegram cleaner must not fire."""
    url = "https://about.meta.com/page?context=1"
    assert deep_clean(url) == url


def test_subdomain_still_matches() -> None:
    assert deep_clean("https://mobile.twitter.com/u/status/1?s=20") == (
        "https://mobile.twitter.com/u/status/1"
    )


def test_query_embedded_url_keeps_double_slash() -> None:
    """post_process must not collapse '//' inside query values."""
    url = "https://example.com/r?url=https://a//b&utm_source=x"
    assert deep_clean(url) == "https://example.com/r?url=https://a//b"


def test_path_double_slash_still_collapsed() -> None:
    assert CleanerUtils.post_process("https://example.com//a//b?x=1") == (
        "https://example.com/a/b?x=1"
    )
