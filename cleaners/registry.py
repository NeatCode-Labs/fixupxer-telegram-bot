"""Registry maps domains → cleaners for O(1) dispatch (mirrors `CleanerRegistry.kt`)."""
from __future__ import annotations

from .base import UrlCleaner

_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "amazon": (
        "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it",
        "amazon.es", "amazon.ca", "amazon.co.jp", "amazon.in",
        "amazon.com.br", "amazon.com.mx", "amazon.com.au",
        "amzn.to", "amzn.eu", "amzn.asia",
    ),
    "google_search": (
        "google.com", "google.co.uk", "google.de", "google.fr",
        "google.it", "google.es", "google.co.jp", "google.ca",
        "google.com.au", "google.co.in", "google.com.br", "google.ru",
        "google.nl", "google.pl", "google.com.mx", "google.co.kr",
    ),
    "youtube": ("youtube.com", "m.youtube.com", "music.youtube.com",
                "youtube-nocookie.com", "youtu.be"),
    "facebook": ("facebook.com", "m.facebook.com", "fb.com", "fb.watch",
                 "facebookez.com"),
    "reddit": ("reddit.com", "old.reddit.com", "new.reddit.com", "redd.it"),
    "twitter": ("twitter.com", "x.com", "fixupx.com", "fxtwitter.com",
                "vxtwitter.com"),
    "instagram": ("instagram.com", "kkinstagram.com", "eeinstagram.com",
                  "instagram7.com", "toinstagram.com", "adamlikes.men",
                  "ddinstagram.com"),
    "tiktok": ("tiktok.com", "vm.tiktok.com", "m.tiktok.com",
               "tiktokcdn.com", "tiktokv.com",
               "tnktok.com", "tfxktok.com", "tiktokez.com", "kktiktok.com",
               "vxtiktok.com", "tiktxk.com"),
    "linkedin": ("linkedin.com", "lnkd.in"),
    "substack": ("substack.com",),
    "pinterest": ("pinterest.com", "pin.it"),
    "snapchat": ("snapchat.com", "snap.com"),
    "discord": ("discord.com", "discord.gg"),
    "telegram_web": ("t.me", "telegram.me"),
    "whatsapp": ("wa.me", "whatsapp.com", "api.whatsapp.com"),
    "twitch": ("twitch.tv",),
    "netflix": ("netflix.com",),
    "spotify": ("spotify.com", "open.spotify.com", "spotify.link"),
    "github": ("github.com",),
    "stackoverflow": ("stackoverflow.com", "stackexchange.com"),
    "ebay": ("ebay.com", "ebay.co.uk", "ebay.de"),
    "shopify": ("myshopify.com",),
    "aliexpress": ("aliexpress.com", "aliexpress.us", "ae.aliexpress.com"),
    "bing": ("bing.com",),
    "duckduckgo": ("duckduckgo.com",),
    "medium": ("medium.com",),
}


def _extract_domain(url: str) -> str | None:
    try:
        without_proto = url.split("://", 1)[-1]
        end = len(without_proto)
        for ch in "/?#:":
            i = without_proto.find(ch)
            if i != -1 and i < end:
                end = i
        domain = without_proto[:end].lower()
        return domain.removeprefix("www.")
    except Exception:
        return None


class CleanerRegistry:
    """Holds all registered UrlCleaner instances and dispatches by domain."""

    def __init__(self) -> None:
        self._all: list[UrlCleaner] = []
        self._domain_map: dict[str, list[UrlCleaner]] = {}

    def register(self, cleaner: UrlCleaner) -> None:
        self._all.append(cleaner)
        for hint in _DOMAIN_HINTS.get(cleaner.id, ()):  # may be empty (e.g. general)
            self._domain_map.setdefault(hint, []).append(cleaner)

    def register_all(self, cleaners: list[UrlCleaner]) -> None:
        for c in cleaners:
            self.register(c)

    def get_cleaners_for(self, url: str) -> list[UrlCleaner]:
        domain = _extract_domain(url)
        if domain and domain in self._domain_map:
            return [c for c in self._domain_map[domain] if c.matches(url)]
        # Fallback: walk every cleaner. The general cleaner always matches and
        # the misc cleaner matches via its own domain set, so they're picked up
        # here when the domain hint table doesn't have an entry.
        return [c for c in self._all if c.matches(url)]

    def all_cleaners(self) -> list[UrlCleaner]:
        return list(self._all)
