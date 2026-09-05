"""URL preprocessing: zero-width strip, IDN ASCII, leading '@' strip.

Mirrors `UrlProcessor.preprocessUrl` in the Android app, plus the IG-share
'@' prefix handling done in app share extras.
"""
from __future__ import annotations

import re
import urllib.parse

_ZERO_WIDTH = re.compile(r"[\u200B\u200C\u200D\uFEFF\u2060]")


def _idn_to_ascii(domain: str) -> str:
    """Convert an IDN to ASCII (Punycode), best-effort."""
    if not domain:
        return domain
    if all(ord(c) < 128 for c in domain):
        return domain  # already ASCII; cheap path
    try:
        import idna  # type: ignore
        return idna.encode(domain, uts46=True).decode("ascii")
    except Exception:
        try:
            return domain.encode("idna").decode("ascii")
        except Exception:
            return domain


def preprocess(url: str) -> str:
    """Apply the same prefilters as the Android app.

    - strip zero-width characters
    - preserve percent-encoding in paths, query values and fragments
    - peel leading '@' (Instagram share targets)
    - convert non-ASCII domain → ASCII via IDNA
    """
    if not url:
        return url

    cleaned = _ZERO_WIDTH.sub("", url).strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]

    # Parse the authority before touching the hostname: ':' may belong to userinfo
    # or IPv6, and reserved characters in the other components must stay encoded.
    try:
        parsed = urllib.parse.urlsplit(cleaned)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return cleaned
        userinfo, marker, authority = parsed.netloc.rpartition("@")
        if not marker:
            authority = parsed.netloc
        if authority.startswith("["):
            return cleaned  # IPv6 literals do not need IDNA conversion.
        host, colon, port = authority.partition(":")
        ascii_host = _idn_to_ascii(host)
        netloc = (userinfo + marker if marker else "") + ascii_host + colon + port
        authority_start = cleaned.index("://") + 3
        return cleaned[:authority_start] + netloc + cleaned[authority_start + len(parsed.netloc):]
    except ValueError:
        return cleaned
