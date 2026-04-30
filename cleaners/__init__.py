"""URL cleaning engine ported from the Android FixupXer app.

Public API:
    deep_clean(url, max_passes=5) -> str   one-shot helper
    CleanerService                          stateful service for advanced use
    DEFAULT_REGISTRY                        pre-populated CleanerRegistry
    preprocess(url) -> str                  IDN + zero-width + decode + @-strip
"""

from .base import CleanerCategory, CleanerUtils, UrlCleaner
from .impl import build_default_registry
from .preprocess import preprocess
from .registry import CleanerRegistry
from .service import CleanerService

DEFAULT_REGISTRY: CleanerRegistry = build_default_registry()
_DEFAULT_SERVICE = CleanerService(DEFAULT_REGISTRY)


def deep_clean(url: str, max_passes: int = 5) -> str:
    """Convenience wrapper that uses the default service + registry."""
    if not url:
        return url
    return _DEFAULT_SERVICE.deep_clean(preprocess(url), max_passes=max_passes)


__all__ = [
    "UrlCleaner",
    "CleanerCategory",
    "CleanerUtils",
    "CleanerRegistry",
    "CleanerService",
    "DEFAULT_REGISTRY",
    "preprocess",
    "deep_clean",
]
