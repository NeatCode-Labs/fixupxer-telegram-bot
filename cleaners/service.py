"""Multi-pass deep-clean service (mirrors `CleanerService.kt`)."""
from __future__ import annotations

import logging
from collections.abc import Callable

from .registry import CleanerRegistry

logger = logging.getLogger(__name__)


def _priority(cleaner_id: str) -> int:
    """Lower runs first.

    1. Extraction (search redirects, short links).
    2. Domain-aware param cleaners that also influence rewrites
       (twitter/instagram/facebook). Domain rewriting itself happens *outside*
       the cleaner pipeline — these only strip params here.
    3. Other domain-specific cleaners.
    4. General fallback (always last).
    """
    cid = cleaner_id.lower()
    if "search" in cid or "redirect" in cid or "short" in cid:
        return 1
    if cid in {"twitter", "instagram", "facebook"}:
        return 2
    if cid in {"general", "general_tracking"}:
        return 4
    return 3


class CleanerService:
    """Runs cleaners iteratively until the URL stabilises (or max_passes hit)."""

    def __init__(self, registry: CleanerRegistry,
                 cache_get: Callable[[str], str | None] | None = None,
                 cache_set: Callable[[str, str], None] | None = None) -> None:
        self._registry = registry
        self._cache_get = cache_get
        self._cache_set = cache_set

    def deep_clean(self, url: str, max_passes: int = 5) -> str:
        if not url:
            return url
        if self._cache_get is not None:
            cached = self._cache_get(url)
            if cached is not None:
                return cached

        current = url
        for _ in range(max_passes):
            cleaners = self._registry.get_cleaners_for(current)
            if not cleaners:
                break
            cleaners.sort(key=lambda c: _priority(c.id))
            next_url = current
            for cleaner in cleaners:
                try:
                    candidate = cleaner.clean(next_url)
                except Exception:
                    logger.exception("Cleaner %s failed on URL %s", cleaner.id, next_url)
                    continue
                if candidate and candidate != next_url:
                    next_url = candidate
            if next_url == current:
                break
            current = next_url

        if self._cache_set is not None:
            try:
                self._cache_set(url, current)
            except Exception:
                logger.exception("Cleaner cache set failed")
        return current
