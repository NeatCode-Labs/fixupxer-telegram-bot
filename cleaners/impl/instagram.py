"""Instagram cleaner — 67 tracking params + 8 preserve params (parity with app)."""
from __future__ import annotations

from ..base import CleanerCategory
from ._base import AggressiveCleaner

_TRACKING = frozenset({
    # Basic
    "igsh", "igshid", "ig_cache_key", "ig_mid",
    "ig_share_sheet", "__a", "__d", "_rdr", "hl",
    # Share
    "share_app_id", "share_sheet_id", "share_id",
    "ig_did", "share_campaign_id", "share_link_id",
    # Analytics & attribution
    "_u_code", "_u_source", "_r", "_t",
    "attribution_link", "ig_nux_id", "ig_referrer",
    # Feed & discovery
    "feed_type", "feed_impression_id", "explore_source",
    "ranking_info_token", "media_id_attribution",
    # Story & reel
    "story_media_owner", "reel_media_owner_id",
    "media_owner_id", "tray_session_id",
    # Engagement
    "like_source", "comment_source", "save_source",
    "share_source", "follow_source", "profile_source",
    # Navigation & UI
    "nav_chain", "from_module", "module_name",
    "entry_point", "surface", "trigger",
    # A/B testing
    "variant", "experiment_group", "test_group",
    "rollout_hash", "version_id",
    # Session & request
    "session_id", "request_id", "query_id",
    "impression_id", "tracking_token",
    # Platform & device
    "device_id", "push_id", "app_id",
    "platform", "os_version", "app_version",
    # Ads & commerce
    "ad_id", "campaign_id", "creative_id",
    "merchant_id", "product_id_override",
    # Legacy
    "taken-by", "tagged_users", "location_id",
})

_PRESERVE = frozenset({
    "img_index",       # Image position in carousel
    "story_media_id",  # Story identifier
    "h",               # Image height
    "w",               # Image width
    "carousel_index",  # Alternative carousel position
    "media_id",        # Direct media reference
    "reel_ids",        # Reel identifiers
    "highlight_reel_ids",
})

InstagramCleaner = AggressiveCleaner(
    id="instagram",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("instagram.com", "kkinstagram.com", "eeinstagram.com", "instagram7.com"),
    tracking=_TRACKING,
    preserve=_PRESERVE,
)
