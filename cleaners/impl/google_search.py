"""Google Search cleaner — extracts the real URL from `/url?q=` redirects."""
from __future__ import annotations

import re
import urllib.parse
from ipaddress import IPv6Address

from ..base import CleanerCategory, CleanerUtils, UrlCleaner

_DOMAINS = (
    "google.com", "google.co.uk", "google.de", "google.fr",
    "google.it", "google.es", "google.co.jp", "google.ca",
    "google.com.au", "google.co.in", "google.com.br", "google.ru",
    "google.nl", "google.pl", "google.com.mx", "google.co.kr",
)

_TRACKING = frozenset({
    "ved", "ei", "usg", "sa", "source", "sourceid",
    "sxsrf", "biw", "bih", "dpr", "cad", "uact",
    "oq", "aq", "aqs", "gs_lcp", "gs_lcrp", "sclient",
    "gs_l", "gs_ssp", "gs_rn", "gs_ri", "gs_mss",
    "rct", "cd", "vet", "esrc", "espv", "cshid",
    "ictx", "sig2", "act", "rc", "jfp",
    "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "gclid", "dclid",
    "bvm", "ion", "prmd", "iflsig", "rlz", "pccc",
    "psi", "stick", "tci", "sqi", "bav", "pf",
    "atyp", "asst", "client", "hs", "authuser",
    "pq", "pdl", "nfpr", "spell", "npsic", "mvs",
    "agsad", "gfe_rd", "gws_rd", "complete", "pval",
    "noj", "btnG", "btnI", "site", "output", "domains",
    "tbm", "ijn", "imgrc", "imgrefurl", "imgurl",
    "docid", "tbnid", "zoom", "vt",
    "sll", "sspn", "vps", "vpsrc", "msa", "msid",
    "mid", "skstate", "rtlr", "rlha", "rllag",
    "cf", "ncl", "ndsp", "nca", "nds", "ncf",
    "psb", "psig", "rflfq", "rldimm", "lsft", "shm",
    "ssta", "sstk", "st", "tch", "tcfs", "rfl",
    "amp", "amp_ct", "amp_url", "ampshare", "usqp",
    "adtest", "adsafe", "adk", "aggsa", "ccd", "dq",
    "npa", "ohost", "opv", "ovss", "pf_rd_i", "pglt",
    "pbx", "rbas", "rbs", "rciv", "tbo",
    "trex", "uule", "uuld", "vld", "zx",
})

_PRESERVE = frozenset({
    "q", "tbm", "tbs", "start", "num",
    "hl", "lr", "safe", "nfpr", "filter",
    "as_q", "as_epq", "as_oq", "as_eq", "as_qdr", "as_rights",
    "imgsz", "imgtype", "imgc", "gl", "cr",
})

_EXACT_HOSTS = frozenset(_DOMAINS) | frozenset("www." + domain for domain in _DOMAINS)
_INVALID_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_INVALID_URL_CHAR = re.compile(r"[\x00-\x20\x7f\\]")
_HOST_LABEL = re.compile(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?")


def _parse_http_url(url: str) -> urllib.parse.SplitResult | None:
    """Validate structure without decoding or canonicalising URL components."""
    if _INVALID_ESCAPE.search(url) or _INVALID_URL_CHAR.search(url):
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if parsed.netloc.endswith(":") or parsed.port == 0:
            return None
        host = parsed.hostname
        if ":" in host:
            IPv6Address(host)
        else:
            ascii_host = host.encode("idna").decode("ascii").removesuffix(".")
            if len(ascii_host) > 253 or not all(
                _HOST_LABEL.fullmatch(label) for label in ascii_host.split(".")
            ):
                return None
        return parsed
    except (ValueError, UnicodeError):
        return None


def _is_google_endpoint(parsed: urllib.parse.SplitResult) -> bool:
    return (parsed.hostname in _EXACT_HOSTS
            and parsed.port in {None, 80 if parsed.scheme == "http" else 443})


class _GoogleSearchCleaner(UrlCleaner):
    id = "google_search"
    category = CleanerCategory.SEARCH_ENGINES

    def matches(self, url: str) -> bool:
        parsed = _parse_http_url(url)
        return bool(parsed and _is_google_endpoint(parsed)
                    and parsed.path in {"/url", "/search"})

    def preserves_query_key(self, url: str, key: str) -> bool:
        return key in _PRESERVE

    def clean(self, url: str) -> str:
        if not self.matches(url):
            return url
        parsed = urllib.parse.urlsplit(url)
        if parsed.path == "/url":
            return self._extract_redirect(url) or url
        if "?" not in url:
            return url

        def decide(key: str, pair: str) -> str | None:
            if key in _PRESERVE:
                return pair
            if key in _TRACKING:
                return None
            return pair
        return CleanerUtils.filter_query(url, decide)

    @staticmethod
    def _extract_redirect(url: str) -> str | None:
        parsed = _parse_http_url(url)
        if not parsed or not _is_google_endpoint(parsed) or parsed.path != "/url":
            return None
        targets = []
        for pair in parsed.query.split("&"):
            key, separator, value = pair.partition("=")
            if CleanerUtils.decode_query_key(key) in {"q", "url"}:
                targets.append(value if separator else "")
        # Conflicting, repeated or empty target parameters are ambiguous.
        if len(targets) != 1 or not targets[0]:
            return None
        try:
            decoded = urllib.parse.unquote(targets[0], errors="strict")
        except UnicodeDecodeError:
            return None
        return decoded if _parse_http_url(decoded) is not None else None


GoogleSearchCleaner = _GoogleSearchCleaner()
