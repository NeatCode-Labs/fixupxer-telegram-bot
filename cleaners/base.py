"""Core cleaner protocol, category enum and URL splitting utilities.

Mirrors `cleaners/UrlCleaner.kt` and `cleaners/utils/CleanerUtils.kt` from
the Android app.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from enum import Enum
from typing import Protocol, runtime_checkable


class CleanerCategory(Enum):
    SOCIAL_MEDIA = "Social Media"
    E_COMMERCE = "E-Commerce"
    SEARCH_ENGINES = "Search Engines"
    VIDEO_PLATFORMS = "Video Platforms"
    NEWS_MEDIA = "News & Media"
    GENERAL = "General"
    OTHER = "Other"


@runtime_checkable
class UrlCleaner(Protocol):
    id: str
    category: CleanerCategory

    def matches(self, url: str) -> bool: ...
    def clean(self, url: str) -> str: ...


class CleanerUtils:
    """Static helpers used by every cleaner.

    Mirrors CleanerUtils.kt: preprocess (fix `&` before `?`), splitUrl (base,
    query, fragment), rebuildUrl (with post-process), keep_or_drop semantics.
    """

    _DOUBLE_SLASH = re.compile(r"/+")

    @staticmethod
    def extract_host(url: str) -> str:
        """Return the lowercased hostname of ``url`` ('' when absent)."""
        without_proto = url.split("://", 1)[-1]
        end = len(without_proto)
        for ch in "/?#:":
            i = without_proto.find(ch)
            if i != -1 and i < end:
                end = i
        return without_proto[:end].lower()

    @staticmethod
    def host_matches(url: str, domains: Iterable[str]) -> bool:
        """True when the URL's *hostname* equals one of ``domains`` or is a
        subdomain of one.

        Substring checks like ``"x.com" in url`` false-positive on path text
        ("/story-about-x.com") and unrelated hosts ("maxx.com", "t.me" inside
        "about.meta.com"); this anchors the match at the host level.
        """
        host = CleanerUtils.extract_host(url)
        if host.startswith("www."):
            host = host[4:]
        return any(host == d or host.endswith("." + d) for d in domains)

    @staticmethod
    def preprocess(url: str) -> str:
        """Fix the common `https://example.com&a=b` glitch (no `?` before `&`)."""
        if "&" in url and "?" not in url:
            first_amp = url.index("&")
            if first_amp > 0:
                before = url[:first_amp]
                if "://" in before and "#" not in before:
                    return url[:first_amp] + "?" + url[first_amp + 1:]
        return url

    @staticmethod
    def post_process(url: str) -> str:
        """Strip empty trailing query/fragment markers and collapse `//` in the path."""
        result = url.rstrip("?&#")
        if "://" in result:
            scheme_end = result.index("://") + 3
            head, tail = result[:scheme_end], result[scheme_end:]
            # Collapse duplicate slashes only up to the query/fragment —
            # query values may legitimately embed full URLs (?next=https://…).
            cut = len(tail)
            for ch in "?#":
                i = tail.find(ch)
                if i != -1 and i < cut:
                    cut = i
            tail = CleanerUtils._DOUBLE_SLASH.sub("/", tail[:cut]) + tail[cut:]
            result = head + tail
        return result

    @staticmethod
    def split_url(url: str) -> tuple[str, str, str]:
        """Return (base, query, fragment) — fragment includes the leading '#' if present."""
        fixed = CleanerUtils.preprocess(url)
        query_start = fixed.find("?")
        if query_start == -1:
            frag_start = fixed.find("#")
            if frag_start == -1:
                return fixed, "", ""
            return fixed[:frag_start], "", fixed[frag_start:]
        base = fixed[:query_start]
        query_and_fragment = fixed[query_start + 1:]
        frag_idx = query_and_fragment.find("#")
        if frag_idx == -1:
            return base, query_and_fragment, ""
        return (
            base,
            query_and_fragment[:frag_idx],
            query_and_fragment[frag_idx:],
        )

    @staticmethod
    def rebuild_url(base: str, parameters: Iterable[str], fragment: str) -> str:
        params_list = [p for p in parameters if p]
        result = base + ("?" + "&".join(params_list) if params_list else "") + fragment
        return CleanerUtils.post_process(result)

    @staticmethod
    def filter_query(
        url: str,
        decide,
    ) -> str:
        """Generic per-pair filter.

        `decide(key, pair)` returns the pair to keep, or None to drop.
        Pairs without a value (e.g. `theater` on Facebook) are passed with
        the whole token as `key`.

        Always goes through ``split_url`` so the ``&`` → ``?`` malformation
        fix is applied (matches CleanerUtils.kt behaviour).
        """
        try:
            base, query, fragment = CleanerUtils.split_url(url)
            if not query:
                return CleanerUtils.rebuild_url(base, [], fragment)
            kept: list[str] = []
            for pair in query.split("&"):
                if not pair:
                    continue
                eq = pair.find("=")
                key = pair if eq == -1 else pair[:eq]
                decision = decide(key, pair)
                if decision:
                    kept.append(decision)
            return CleanerUtils.rebuild_url(base, kept, fragment)
        except Exception:  # noqa: BLE001 — match Kotlin "on error, return original"
            return url
