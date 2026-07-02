"""Lightweight cleaners for platforms without dedicated tracking lists in the app.

Each entry below corresponds to a section in `SUPPORTED_PLATFORMS.md`. We keep
unknown params (since these aren't fully spec'd) and only drop the documented
tracking parameters — i.e. *non-aggressive* mode. This is the safest mirror of
the app's behaviour for these "long tail" sites.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..base import CleanerCategory, CleanerUtils, UrlCleaner


class _DomainBlocklistCleaner(UrlCleaner):
    """Match by domain set; remove any param in `tracking`; keep the rest."""

    def __init__(
        self,
        id: str,
        category: CleanerCategory,
        domains: Sequence[str],
        tracking: Sequence[str],
    ) -> None:
        self.id = id
        self.category = category
        self._domains = tuple(d.lower() for d in domains)
        self._tracking = frozenset(tracking)

    def matches(self, url: str) -> bool:
        return CleanerUtils.host_matches(url, self._domains)

    def clean(self, url: str) -> str:
        if "?" not in url:
            return url
        tracking = self._tracking

        def decide(key: str, pair: str) -> str | None:
            if key in tracking:
                return None
            return pair
        return CleanerUtils.filter_query(url, decide)


PinterestCleaner = _DomainBlocklistCleaner(
    id="pinterest",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("pinterest.com", "pin.it"),
    tracking=(
        "e_t", "e_t_s", "e_t_cs", "ouuid", "cid",
        "sfo", "sfo_s", "nic", "nic_v", "pin_unauth",
        "dpi", "i", "w", "m", "n",
    ),
)

SnapchatCleaner = _DomainBlocklistCleaner(
    id="snapchat",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("snapchat.com", "snap.com"),
    tracking=("share_id", "locale", "attachment_url"),
)

DiscordCleaner = _DomainBlocklistCleaner(
    id="discord",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("discord.com", "discord.gg"),
    tracking=("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"),
)

TelegramWebCleaner = _DomainBlocklistCleaner(
    id="telegram_web",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("t.me", "telegram.me"),
    tracking=("tgme",),  # leave start/startgroup/game/voicechat alone (they're functional)
)

WhatsAppCleaner = _DomainBlocklistCleaner(
    id="whatsapp",
    category=CleanerCategory.SOCIAL_MEDIA,
    domains=("wa.me", "whatsapp.com", "api.whatsapp.com"),
    tracking=("app_absent", "link_medium", "link_source"),
)

TwitchCleaner = _DomainBlocklistCleaner(
    id="twitch",
    category=CleanerCategory.VIDEO_PLATFORMS,
    domains=("twitch.tv",),
    tracking=("tt_medium", "tt_content"),
)

NetflixCleaner = _DomainBlocklistCleaner(
    id="netflix",
    category=CleanerCategory.VIDEO_PLATFORMS,
    domains=("netflix.com",),
    tracking=("trackId", "tctx", "jb", "jbv", "dgs"),
)

SpotifyCleaner = _DomainBlocklistCleaner(
    id="spotify",
    category=CleanerCategory.OTHER,
    domains=("spotify.com", "open.spotify.com", "spotify.link"),
    tracking=("si", "dl_branch", "dl_mobileapp", "go", "nd"),
)

GitHubCleaner = _DomainBlocklistCleaner(
    id="github",
    category=CleanerCategory.OTHER,
    domains=("github.com",),
    tracking=("email_token", "email_source"),
)

StackOverflowCleaner = _DomainBlocklistCleaner(
    id="stackoverflow",
    category=CleanerCategory.OTHER,
    domains=("stackoverflow.com", "stackexchange.com"),
    tracking=("rq", "rv", "lq", "md"),
)

EbayCleaner = _DomainBlocklistCleaner(
    id="ebay",
    category=CleanerCategory.E_COMMERCE,
    domains=("ebay.com", "ebay.co.uk", "ebay.de"),
    tracking=(
        "mkrid", "siteid", "mkcid", "mkevt", "mkpid",
        "trksid", "campid", "toolid", "customid", "amdata",
    ),
)

ShopifyCleaner = _DomainBlocklistCleaner(
    id="shopify",
    category=CleanerCategory.E_COMMERCE,
    domains=("myshopify.com",),
    tracking=(
        "omnisendContactID", "sca_ref", "mc_cid", "mc_eid",
        "_pos", "_sid", "_ss", "_s", "_shopify_s",
        "_shopify_sa_t", "_shopify_sa_p", "_shopify_y", "cart_sig",
    ),
)

AliExpressCleaner = _DomainBlocklistCleaner(
    id="aliexpress",
    category=CleanerCategory.E_COMMERCE,
    domains=("aliexpress.com", "aliexpress.us", "ae.aliexpress.com"),
    tracking=(
        "spm", "scm", "scm_id", "scm-url", "pvid",
        "algo_expid", "algo_pvid", "ns", "abbucket", "acm",
        "utparam", "pos", "cv", "af", "mall_affr", "sk", "dp",
        "terminal_id", "aff_fcid", "aff_fsk", "aff_platform",
        "aff_trace_key", "shareId", "businessType", "title",
        "srcSns", "image", "sourceType", "spreadType", "templateId",
    ),
)

BingCleaner = _DomainBlocklistCleaner(
    id="bing",
    category=CleanerCategory.SEARCH_ENGINES,
    domains=("bing.com",),
    tracking=(
        "cvid", "FORM", "qpvt", "qs", "sc", "sp", "sk",
        "ghsh", "ghacc", "ghpl", "ghpr", "ghc", "ghhc", "ghpos",
    ),
)

DuckDuckGoCleaner = _DomainBlocklistCleaner(
    id="duckduckgo",
    category=CleanerCategory.SEARCH_ENGINES,
    domains=("duckduckgo.com",),
    tracking=("t", "ia", "iax", "atb", "v7-it"),
)

MediumCleaner = _DomainBlocklistCleaner(
    id="medium",
    category=CleanerCategory.NEWS_MEDIA,
    domains=("medium.com",),
    tracking=("source", "sk", "source_user_id", "source_post_link"),
)

ALL_MISC = (
    PinterestCleaner, SnapchatCleaner, DiscordCleaner, TelegramWebCleaner,
    WhatsAppCleaner, TwitchCleaner, NetflixCleaner, SpotifyCleaner,
    GitHubCleaner, StackOverflowCleaner, EbayCleaner, ShopifyCleaner,
    AliExpressCleaner, BingCleaner, DuckDuckGoCleaner, MediumCleaner,
)
