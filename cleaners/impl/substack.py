"""Substack cleaner — only `publication_id` and `post_id` survive."""
from __future__ import annotations

from ..base import CleanerCategory
from ._base import AggressiveCleaner

_TRACKING = frozenset({
    "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "utm_id",
    "isFreemail", "isFromEmail", "email_source",
    "email_type", "email_id", "email_click",
    "r", "ref", "referrer", "token", "access_token",
    "auth_token", "jwt", "session_id",
    "source", "src", "origin", "attribution",
    "attribution_id", "attribution_source",
    "action", "clicked", "opened", "shared",
    "forwarded", "replied", "reaction",
    "experiment", "variant", "test", "bucket",
    "ab_test", "feature_flag", "rollout",
    "newsletter_id", "edition_id", "issue_id",
    "subscriber_id", "list_id", "segment_id",
    "social_source", "social_action", "social_network",
    "tw_source", "fb_source", "li_source",
    "app_source", "app_version", "device_id",
    "platform", "os_version", "app_link",
    "payment_source", "subscription_source",
    "trial_source", "upgrade_source", "plan_id",
    "nav_source", "nav_type", "entry_point",
    "exit_point", "page_source", "section",
    "comment_id", "reply_to", "thread_id",
    "notification_id", "notif_type",
    "search_source", "search_term", "discovery_source",
    "recommendation_source", "suggested_by",
    "timestamp", "ts", "time", "date",
    "expires", "exp", "iat", "nbf",
})

_PRESERVE = frozenset({"publication_id", "post_id"})

SubstackCleaner = AggressiveCleaner(
    id="substack",
    category=CleanerCategory.NEWS_MEDIA,
    domains=("substack.com",),
    tracking=_TRACKING,
    preserve=_PRESERVE,
)
