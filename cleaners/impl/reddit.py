"""Reddit cleaner — short-link path mirrors `RedditCleaner.kt`."""
from __future__ import annotations

from ..base import CleanerCategory, UrlCleaner

_TRACKING = frozenset({
    "context", "correlator", "rdt_cid", "share_id",
    "ref_source", "ref_campaign", "ref_share",
    "_branch_match_id", "_branch_referrer", "_bta_tid",
    "app", "app_name", "app_id", "device_id",
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "utm_id", "utm_name", "utm_reader",
    "session_id", "request_id", "correlation_id",
    "impression_id", "experiment_id", "variant_id",
    "share", "shared_via", "share_from", "share_source",
    "source", "medium", "campaign", "$deep_link",
    "nav_source", "entry_point", "surface", "trigger",
    "source_element", "action_source", "ref_ui",
    "variant", "experiment", "treatment", "bucket",
    "feature", "rollout_hash", "test_group",
    "notification_id", "message_id", "email_id",
    "push_id", "alert_id", "digest_id",
    "ad_id", "campaign_id", "creative_id", "placement_id",
    "promoted", "sponsor_id", "attribution_id",
    "feed_sort", "timeline_sort", "feed_position",
    "nsfw_reason", "quarantine_opt_in", "show_media",
    "award_id", "coin_reward_id", "coin_bonus_id",
    "gilding_detail", "award_type", "is_anonymous",
    "chat_id", "channel_id", "thread_id", "invite_code",
    "chat_subreddit_id", "member_count",
    "st", "sh", "s", "dest", "id_token", "state",
    "quicklink", "subredditName", "creation_source",
})

_PRESERVE = frozenset({
    "context", "sort", "t", "q", "type",
    "restrict_sr", "include_over_18",
    "after", "before", "limit", "count",
    "show", "raw_json", "depth", "showmore",
    "sr_detail", "sr", "is_multi", "ref",
})


class _RedditCleaner(UrlCleaner):
    id = "reddit"
    category = CleanerCategory.SOCIAL_MEDIA

    def matches(self, url: str) -> bool:
        lower = url.lower()
        return "reddit.com" in lower or "redd.it" in lower

    def clean(self, url: str) -> str:
        # redd.it short-links: drop the entire query string (matches app).
        if "redd.it" in url.lower():
            q = url.find("?")
            return url if q == -1 else url[:q]
        if "?" not in url:
            return url
        from ..base import CleanerUtils

        def decide(key: str, pair: str) -> str | None:
            if key in _PRESERVE:
                return pair
            if key in _TRACKING:
                return None
            return None
        return CleanerUtils.filter_query(url, decide)


RedditCleaner = _RedditCleaner()
