"""YouTube cleaner — special handling for `youtu.be/` short links and `music.youtube.com`."""
from __future__ import annotations

import re

from ..base import CleanerCategory, CleanerUtils, UrlCleaner

_TRACKING = frozenset({
    "si", "pp", "feature", "app", "attribution_link",
    "embeds_referring_euri", "embeds_referring_origin",
    "embeds_euri", "source_ve_path", "gclid", "ytclid",
    "share", "shared_via", "ref", "referer", "referrer",
    "fbclid", "sms_ss", "ucbcb", "share_source",
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "utm_id", "utm_reader", "utm_pubreferrer",
    "session_id", "ei", "ved", "sourceid", "ssfr",
    "continuation", "itct", "ctoken", "sttm",
    "lact", "action_name", "action_type", "annotation_id",
    "src_vid", "feature_id", "c", "client",
    "redir_token", "next", "flow", "entry_point",
    "bp", "sp", "sr_origin", "algo", "aq",
    "app_version", "app_name", "device_id", "install_id",
    "app_install_ctx", "vndapp", "vndclient", "mweb",
    "variant", "experiment_id", "bucket", "treatment",
    "version_id", "test_group", "disable_polymer",
    "rec_id", "recommendation_info", "shelf_id",
    "video_id_list", "suggested_video_id", "rv",
    "notification_id", "notification_type", "alert_type",
    "push_id", "email_id", "sms_id",
    "search_sort", "search_filter", "search_type",
    "search_token", "query_source", "suggested_by",
    "ad_id", "campaign_id", "creative_id", "placement_id",
    "ad_type", "ad_signal", "autonav", "autoplay",
    "channel_feature", "creator_channel_id", "ab_beacon",
    "subscribe_feature", "notification_menu_feature",
    "playnext", "shuffle", "mix_id",
    "bpctr", "pbjreload", "pbj", "hl", "gl", "persist_hl",
    "persist_gl", "has_verified", "nohtml5", "html5",
    "spfreload", "disable_related_pause_replay", "ytrcc",
    "vvt", "vl", "vq", "vss_host", "vps", "vpst", "vpstf",
    "vpsrc", "w", "h", "bh", "bw", "adsense_video_doc_id",
    "annotation_src", "endscreen_src", "iv_load_policy",
    "iv_allow_external_links", "iv_endscreen_url",
    "annotation_3_module", "cid", "cin", "cver",
})

_PRESERVE = frozenset({
    "v", "t", "list", "index", "start", "end",
    "ab_channel", "search_query", "q", "radio",
    "p", "page", "sort", "view", "shelf_id", "nolist",
})

# Music adds "si" and "radio" back as preserved.
_MUSIC_PRESERVE = _PRESERVE | {"radio", "si"}

_SHORT_VIDEO_RE = re.compile(r"youtu\.be/([a-zA-Z0-9_-]{11})")
_TIMESTAMP_RE = re.compile(r"[?&]t=([0-9]+[hms]?[0-9]*[ms]?[0-9]*s?)")
_LIST_RE = re.compile(r"[?&]list=([a-zA-Z0-9_-]+)")


class _YouTubeCleaner(UrlCleaner):
    id = "youtube"
    category = CleanerCategory.VIDEO_PLATFORMS

    def matches(self, url: str) -> bool:
        lower = url.lower()
        return any(host in lower for host in (
            "youtube.com", "youtu.be", "youtube-nocookie.com", "music.youtube.com",
        ))

    def clean(self, url: str) -> str:
        if "youtu.be/" in url:
            return self._clean_short(url)
        if "music.youtube.com" in url:
            return self._clean_with(url, _MUSIC_PRESERVE)
        return self._clean_with(url, _PRESERVE)

    def _clean_short(self, url: str) -> str:
        match = _SHORT_VIDEO_RE.search(url)
        if not match:
            return self._clean_with(url, _PRESERVE)
        video_id = match.group(1)
        params: list[str] = []
        ts = _TIMESTAMP_RE.search(url)
        if ts:
            params.append(f"t={ts.group(1)}")
        lst = _LIST_RE.search(url)
        if lst:
            params.append(f"list={lst.group(1)}")
        out = f"https://youtu.be/{video_id}"
        if params:
            out += "?" + "&".join(params)
        return out

    def _clean_with(self, url: str, preserve: frozenset) -> str:
        if "?" not in url:
            return url

        def decide(key: str, pair: str) -> str | None:
            if key in preserve:
                return pair
            if key in _TRACKING:
                return None
            return None
        return CleanerUtils.filter_query(url, decide)


YouTubeCleaner = _YouTubeCleaner()
