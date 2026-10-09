"""Clean Instagram permalinks and known tracking keys."""
from __future__ import annotations

import re
import urllib.parse

from ..base import CleanerCategory
from ._base import AggressiveCleaner

_TRACKING = frozenset({
    # Basic
    "igsh", "igshid", "stkn", "igsi", "ig_rid", "ig_cache_key", "ig_mid",
    "ig_share_sheet", "__a", "__d", "_rdr", "hl",
    # Share
    "share_app_id", "share_sheet_id", "share_id", "exln", "obrf",
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

_CANONICAL_POST_PATH = re.compile(
    r"^/(?P<username>[A-Za-z0-9._]+/)?(?:p|reel|reels|tv)/[A-Za-z0-9_-]+/?$"
)
_CANONICAL_ORIGIN_HOSTS = frozenset({
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
})
_RESERVED_PREFIXES = frozenset({
    ".", "..", "share", "accounts", "oauth", "explore", "direct", "stories",
})
_POSITIVE_INTEGER = re.compile(r"^[0-9]+$")
_MAX_IMG_INDEX = 2_147_483_647


class _InstagramCleaner(AggressiveCleaner):
    """Use path-aware query removal only for first-party public post permalinks."""

    def clean(self, url: str) -> str:
        canonical = self._clean_canonical_post(url)
        if canonical is not None:
            return canonical
        # Proxy URLs, special routes, malformed authorities and other paths keep
        # the established exact-key policy and preserve unknown values/fragments.
        return super().clean(url)

    @staticmethod
    def _clean_canonical_post(url: str) -> str | None:
        # Match the bot's URL intake guard before applying the broader policy.
        # Invalid inputs fall back to the established per-key cleaner.
        if re.search(r"[\x00-\x20\x7f\\]", url) or re.search(r"%(?![0-9a-fA-F]{2})", url):
            return None
        try:
            parsed = urllib.parse.urlsplit(url)
            scheme = parsed.scheme.lower()
            if (
                scheme not in {"http", "https"}
                or parsed.username is not None
                or parsed.password is not None
            ):
                return None
            host = (parsed.hostname or "").lower()
            if host not in _CANONICAL_ORIGIN_HOSTS:
                return None
            default_port = 80 if scheme == "http" else 443
            port = parsed.port
            if port not in (None, default_port):
                return None
            authority = parsed.netloc.lower()
            if (port is None and authority != host) or (
                port is not None and not authority.startswith(f"{host}:")
            ):
                return None
        except ValueError:
            return None

        path_match = _CANONICAL_POST_PATH.fullmatch(parsed.path)
        if path_match is None:
            return None
        username = path_match.group("username")
        if username and username[:-1].lower() in _RESERVED_PREFIXES:
            return None

        values: list[int | None] = []
        for pair in parsed.query.split("&") if parsed.query else ():
            key, separator, value = pair.partition("=")
            if key != "img_index":
                continue
            if not separator or not _POSITIVE_INTEGER.fullmatch(value):
                values.append(None)
                continue
            significant_digits = value.lstrip("0")
            if not significant_digits or len(significant_digits) > 10:
                values.append(None)
                continue
            number = int(significant_digits)
            values.append(number if 1 <= number <= _MAX_IMG_INDEX else None)

        # Repeated selectors are safe only when every value resolves to the same
        # valid integer. Normalize leading zeroes and discard ambiguous values.
        img_index = values[0] if values and values[0] is not None else None
        if img_index is not None and any(value != img_index for value in values):
            img_index = None

        base = url.split("?", 1)[0].split("#", 1)[0]
        return f"{base}?img_index={img_index}" if img_index is not None else base


InstagramCleaner = _InstagramCleaner(
    id="instagram",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=(
        "instagram.com",
        "eeinstagram.com",
        "instagram7.com",
        "ddinstagram.com",
        "adamlikes.men",
        "toinstagram.com",
    ),
    tracking=_TRACKING,
    preserve=_PRESERVE,
)
