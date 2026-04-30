"""Facebook cleaner — 119 tracking params + 19 preserve params (parity with app)."""
from __future__ import annotations

from ..base import CleanerCategory
from ._base import AggressiveCleaner

_TRACKING = frozenset({
    # Basic
    "fbclid", "__cft__", "__tn__", "mibextid", "epa", "_gl",
    "fb_action_ids", "fb_action_types", "fb_source", "fb_ref",
    # Share & referral
    "share_id", "share_source", "share_campaign", "share_medium",
    "_branch_match_id", "_branch_referrer", "branch_data",
    # Analytics & attribution
    "fb_comment_id", "fb_story_location", "fb_dtsg_ag",
    "attribution_id", "attribution_link", "click_id",
    # Feed & timeline
    "feed_story_type", "timeline_context_item_type",
    "timeline_context_item_source", "privacy_mutation_token",
    # Engagement
    "action_history", "action_type_map", "action_ref_map",
    "reaction_type", "reaction_surface", "like_source",
    # Navigation
    "nav_source", "entry_point", "surface", "trigger",
    "ref_type", "ref_component", "ref_page", "ref_module",
    # Mobile app
    "app_id", "app_data", "device_id", "install_id",
    "advertising_id", "limit_ad_tracking", "push_id",
    # A/B testing
    "variant", "experiment", "treatment", "bucket",
    "version_id", "rollout_hash", "test_group", "qe_info",
    # Session & request
    "session_id", "request_id", "query_id", "impression_id",
    "tracking_id", "correlation_id", "client_token",
    # Video & media
    "video_id", "media_id", "media_set", "media_type",
    "play_location", "video_time_position", "video_view_time",
    # Notification
    "notif_type", "alert_id",
    "push_campaign", "email_id", "sms_id",
    # Groups & pages
    "group_id", "page_id", "page_internal", "admin_panel_tab",
    "business_id", "asset_id", "content_id",
    # Ads & commerce
    "ad_id", "campaign_id", "creative_id", "placement_id",
    "audience_id", "boost_id", "promotion_id", "product_id",
    # Messenger
    "messaging_source", "source_id", "alert_message_id",
    "thread_id", "message_id", "mailbox_id",
    # Privacy
    "privacy_source", "privacy_mutation_source", "consent_id",
    "gdpr_consent", "data_policy_version",
    # Legacy & misc
    "sfnsn", "s", "hc", "hc_ref",
    "pn_ref", "aref", "medium", "linkshim", "next",
    "acontext", "paipv", "entrypoint", "fref", "rc",
})

_PRESERVE = frozenset({
    "id", "story_fbid", "fbid",
    "set", "type", "theater",
    "av", "v", "locale", "ref", "hc_location",
    "comment_id", "reply_comment_id",
    "notif_id", "notif_t",
    "tab", "sk", "filter", "section",
})

FacebookCleaner = AggressiveCleaner(
    id="facebook",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("facebook.com", "fb.com", "fb.watch", "facebookez.com", "m.facebook.com"),
    tracking=_TRACKING,
    preserve=_PRESERVE,
)
