"""URL preprocessing: zero-width strip, IDN ASCII, URL decode, leading '@' strip.

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
    - URL-decode percent-encoded characters once (so cleaners see real keys)
    - peel leading '@' (Instagram share targets)
    - convert non-ASCII domain → ASCII via IDNA
    """
    if not url:
        return url

    cleaned = _ZERO_WIDTH.sub("", url).strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]

    # Preserve scheme. Decode only once (further passes can break '%' inside URLs).
    try:
        decoded = urllib.parse.unquote(cleaned)
    except Exception:
        decoded = cleaned

    # IDN → ASCII for the host portion only.
    if "://" in decoded:
        scheme, rest = decoded.split("://", 1)
        end = len(rest)
        for ch in "/?#:":
            i = rest.find(ch)
            if i != -1 and i < end:
                end = i
        host = rest[:end]
        ascii_host = _idn_to_ascii(host)
        decoded = f"{scheme}://{ascii_host}{rest[end:]}"

    return decoded
