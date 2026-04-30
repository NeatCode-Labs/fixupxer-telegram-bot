"""TikTok cleaner — 124 tracking params + 16 preserve params (parity with app)."""
from __future__ import annotations

from ..base import CleanerCategory
from ._base import AggressiveCleaner

_TRACKING = frozenset({
    "_r", "_t", "_d", "tt_from", "tt_content", "share_source",
    "u_code", "preview_pb", "share_app_id", "share_link_id",
    "share_item_id", "share_author_id", "share_app_name",
    "timestamp", "utm_source", "utm_campaign", "utm_medium",
    "enter_from", "enter_method", "from_page", "refer",
    "referer_url", "referer_video_id", "anchor_id", "source",
    "session_id", "request_id", "webcast_app_id", "room_id",
    "sec_user_id", "sec_uid", "u_ser", "user_id",
    "device_platform", "device_type", "browser_language",
    "browser_name", "browser_version", "os_version",
    "screen_width", "screen_height", "client_ab_test",
    "previous_page", "current_page", "depth", "tab_name",
    "gd_label", "category_name", "schema_type", "obj_id",
    "item_id", "group_id", "music_id", "mix_id", "poi_id",
    "region", "priority_region", "language", "verifyFp",
    "live_id", "from_source", "stream_id", "webcast_sdk_version",
    "webcast_language", "webcast_locale", "room_token",
    "pdp_item_id", "shop_id", "product_id", "promotion_id",
    "cart_id", "checkout_id", "payment_id", "order_id",
    "campaign_id", "ad_id", "creative_id", "placement_id",
    "ad_tag", "traffic_type", "is_ads", "ads_creative_id",
    "test_id", "variant_id", "experiment_id", "version_id",
    "bucket_id", "layer_id", "service_id", "strategy_id",
    "app", "app_name", "app_language", "carrier", "mcc_mnc",
    "sys_language", "tz_name", "residence", "is_copy_url",
    "is_from_self", "is_from_friend", "relation_type",
    "social_info", "group_source", "click_reason",
    "checksum", "cursor", "count", "offset", "openudid",
    "uuid", "_aem", "_aem_test", "msToken", "X-Bogus",
    "magic", "scene", "comment_id", "reply_id", "question_id",
    "sticker_id", "effect_id", "filter_id", "game_id",
})

_PRESERVE = frozenset({
    "lang", "q", "t", "embed",
    "video_id", "item_id", "modal",
    "search_keyword", "sort_type", "content_type",
    "creation_time", "hashtag", "sound", "effect",
    "display_method", "is_fullscreen",
})

TikTokCleaner = AggressiveCleaner(
    id="tiktok",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("tiktok.com", "tiktokcdn.com", "tiktokv.com"),
    tracking=_TRACKING,
    preserve=_PRESERVE,
)
