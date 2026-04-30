"""Default cleaner registry — assembles all per-platform cleaners."""
from __future__ import annotations

from ..registry import CleanerRegistry
from .amazon import AmazonCleaner
from .facebook import FacebookCleaner
from .general import GeneralTrackingCleaner
from .google_search import GoogleSearchCleaner
from .instagram import InstagramCleaner
from .linkedin import LinkedInCleaner
from .misc import ALL_MISC
from .reddit import RedditCleaner
from .substack import SubstackCleaner
from .tiktok import TikTokCleaner
from .twitter import TwitterCleaner
from .youtube import YouTubeCleaner


def build_default_registry() -> CleanerRegistry:
    """Return a registry populated with every cleaner shipped with the bot."""
    registry = CleanerRegistry()
    registry.register_all([
        # Domain conversions / extraction first, parameter cleanup second
        # (priority is enforced inside CleanerService).
        TwitterCleaner,
        InstagramCleaner,
        FacebookCleaner,
        YouTubeCleaner,
        TikTokCleaner,
        RedditCleaner,
        LinkedInCleaner,
        AmazonCleaner,
        GoogleSearchCleaner,
        SubstackCleaner,
        *ALL_MISC,
        GeneralTrackingCleaner,
    ])
    return registry


__all__ = ["build_default_registry"]
