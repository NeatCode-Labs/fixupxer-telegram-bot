"""Shared helper used by every per-domain cleaner.

The Android app uses an "aggressive" pattern in 9/11 cleaners:
  - Keep parameters that appear in `preserve_params`
  - Drop parameters that appear in `tracking_params`
  - Drop everything else (unknown == probably tracking)

`extra_keep_predicate` provides an escape hatch (e.g. LinkedIn keeps `f_*`).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

from ..base import CleanerCategory, CleanerUtils, UrlCleaner


class AggressiveCleaner(UrlCleaner):
    """Generic UrlCleaner: domain set + tracking set + preserve set."""

    def __init__(
        self,
        id: str,
        category: CleanerCategory,
        domains: Iterable[str],
        tracking: Iterable[str],
        preserve: Iterable[str],
        *,
        extra_keep_predicate: Callable[[str], bool] | None = None,
    ) -> None:
        self.id = id
        self.category = category
        self._domains = tuple(d.lower() for d in domains)
        self._tracking = frozenset(tracking)
        self._preserve = frozenset(preserve)
        self._extra_keep = extra_keep_predicate

    def matches(self, url: str) -> bool:
        lower = url.lower()
        return any(domain in lower for domain in self._domains)

    def clean(self, url: str) -> str:
        if "?" not in url:
            return url
        preserve = self._preserve
        tracking = self._tracking
        extra_keep = self._extra_keep

        def decide(key: str, pair: str) -> str | None:
            if key in preserve:
                return pair
            if extra_keep is not None and extra_keep(key):
                return pair
            if key in tracking:
                return None
            return None  # aggressive: drop unknown
        return CleanerUtils.filter_query(url, decide)
