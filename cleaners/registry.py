"""Registry maps domains → cleaners for O(1) dispatch (mirrors `CleanerRegistry.kt`)."""
from __future__ import annotations

import re
from collections.abc import Iterable

from .base import CleanerCategory, CleanerUtils, UrlCleaner

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
    "facebook": ("facebook.com", "m.facebook.com", "fb.com", "fb.watch"),
    "reddit": ("reddit.com", "old.reddit.com", "new.reddit.com", "redd.it"),
    "twitter": ("twitter.com", "x.com", "fixupx.com", "fxtwitter.com",
                "vxtwitter.com"),
    "instagram": ("instagram.com", "eeinstagram.com",
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
    return CleanerUtils.extract_host(url).removeprefix("www.") or None


class CleanerRegistry:
    """Holds all registered UrlCleaner instances and dispatches by domain."""

    def __init__(self) -> None:
        self._all: list[UrlCleaner] = []
        self._domain_map: dict[str, list[UrlCleaner]] = {}
        self._general: list[UrlCleaner] = []
        self._proxy_cleaners: list[tuple[UrlCleaner, tuple[str, ...]]] = []

    def register(self, cleaner: UrlCleaner) -> None:
        self._all.append(cleaner)
        if cleaner.category == CleanerCategory.GENERAL:
            self._general.append(cleaner)
        for hint in _DOMAIN_HINTS.get(cleaner.id, ()):  # may be empty (e.g. general)
            self._domain_map.setdefault(hint, []).append(cleaner)

    def register_all(self, cleaners: list[UrlCleaner]) -> None:
        for c in cleaners:
            self.register(c)

    def configure_proxy_domains(
        self, *, instagram: Iterable[str] = (), tiktok: Iterable[str] = (),
    ) -> None:
        """Replace this registry's Instagram/TikTok proxy aliases at startup.

        Call before populating a service's result cache. Cleaner singletons and
        other registry instances remain unchanged; repeating a call is idempotent.
        Invalid, retired or conflicting domains fail without changing the registry.
        """
        configured = {
            "instagram": tuple(dict.fromkeys(d.strip().lower().rstrip(".") for d in instagram)),
            "tiktok": tuple(dict.fromkeys(d.strip().lower().rstrip(".") for d in tiktok)),
        }
        aliases = []
        for platform, domains in configured.items():
            cleaner = next((c for c in self._all if c.id == platform), None)
            if domains and cleaner is None:
                raise ValueError(f"Register the {platform} cleaner before configuring its proxies")
            for domain in domains:
                if len(domain) > 253 or not re.fullmatch(
                    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", domain,
                ):
                    raise ValueError("Proxy aliases must be bare DNS hostnames")
                reserved = (
                    "facebookez.com", "kkinstagram.com",
                    *(hint for cid, hints in _DOMAIN_HINTS.items() if cid != platform
                      for hint in hints),
                    *(other for cid, values in configured.items() if cid != platform
                      for other in values),
                )
                if any(domain == other or domain.endswith("." + other)
                       or other.endswith("." + domain) for other in reserved):
                    raise ValueError("Proxy aliases must not overlap retired or other platform hosts")
            if cleaner is not None and domains:
                aliases.append((cleaner, domains))
        self._proxy_cleaners = aliases

    def get_cleaners_for(self, url: str) -> list[UrlCleaner]:
        domain = _extract_domain(url)
        aliases = [cleaner for cleaner, domains in self._proxy_cleaners
                   if CleanerUtils.host_matches(url, domains)]
        if domain and domain in self._domain_map:
            matched = [c for c in self._domain_map[domain] + self._general if c.matches(url)]
        else:
            # Unknown subdomains use the ordinary matches predicates.
            matched = [c for c in self._all if c.matches(url)]
        # An alias is local dispatch metadata, not a mutation of the shared
        # cleaner's own domain list. Avoid duplicates when an alias is built-in.
        return list({id(cleaner): cleaner for cleaner in matched + aliases}.values())

    def all_cleaners(self) -> list[UrlCleaner]:
        return list(self._all)
