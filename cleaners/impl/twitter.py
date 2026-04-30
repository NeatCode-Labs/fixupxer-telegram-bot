"""Twitter/X cleaner — 99 tracking params + 11 preserve params (parity with app)."""
from __future__ import annotations

from ..base import CleanerCategory
from ._base import AggressiveCleaner

_TRACKING = frozenset({
    # Basic
    "s", "t", "ref_src", "ref_url", "via", "__twitter_impression", "cn", "src",
    # Share & referral
    "share", "shared_via", "ref", "referer",
    "twclid", "twgr", "twcamp", "twterm",
    # Analytics & attribution
    "impression_id", "promoted_content", "click_id",
    "attribution_id", "attribution_link", "source",
    # Timeline & feed
    "timeline_id", "tweet_mode", "tweet_result_type",
    "include_entities", "include_rts", "exclude_replies",
    # Engagement
    "like_source", "retweet_source", "reply_source",
    "follow_source", "unfollow_source", "block_source",
    # Navigation
    "nav_source", "entry_point", "surface", "trigger",
    "context", "mx", "mi", "mk", "mz",
    # Mobile app
    "app", "app_name", "app_id", "device_id",
    "install_id", "advertising_id", "limit_ad_tracking",
    # A/B testing
    "variant", "bucket", "experiment", "treatment",
    "version_id", "rollout_hash", "test_group",
    # Session & request
    "session_id", "request_id", "query_id",
    "cursor", "max_id", "since_id", "count",
    # Card & media
    "card_name", "card_url", "media_id",
    "media_tags", "tagged_users", "place_id",
    # Notification
    "notif_id", "notif_type", "notif_source",
    "push_id", "email_id", "sms_id",
    # Search & discovery
    "q_source", "result_type", "vertical",
    "f", "src_hashtag", "src_trend",
    # Ads & promoted
    "ad_id", "campaign_id", "creative_id",
    "advertiser_id", "placement_id", "targeting_criteria",
    # Twitter Blue / Premium
    "premium_source", "subscription_source", "feature_source",
    "blue_verified", "premium_tier",
    # Legacy
    "tw_p", "tw_i", "tw_u", "tw_o",
    "original_referer", "uprof",
})

_PRESERVE = frozenset({
    "lang", "theme", "display", "tz",
    "include_profile_interstitial_type",
    "include_blocking", "include_blocked_by",
    "include_followed_by", "include_want_retweets",
    "include_mute_edge", "include_can_dm",
})

TwitterCleaner = AggressiveCleaner(
    id="twitter",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("twitter.com", "x.com", "fixupx.com", "fxtwitter.com", "vxtwitter.com"),
    tracking=_TRACKING,
    preserve=_PRESERVE,
)
