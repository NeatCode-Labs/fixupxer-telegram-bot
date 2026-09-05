"""Shared domain cleaner: preserve functional and unknown parameters.

The historical class name is retained for callers, but only known tracking
parameters are removed. `extra_keep_predicate` protects functional key families.
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
        return CleanerUtils.host_matches(url, self._domains)

    def preserves_query_key(self, url: str, key: str) -> bool:
        return key in self._preserve or bool(self._extra_keep and self._extra_keep(key))

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
            return pair
        return CleanerUtils.filter_query(url, decide)
