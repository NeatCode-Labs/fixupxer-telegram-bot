"""Google Search cleaner — extracts the real URL from `/url?q=` redirects."""
from __future__ import annotations

import re
import urllib.parse

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

_REDIRECT_PATTERNS = (
    re.compile(r"[?&]url=([^&]+)"),
    re.compile(r"[?&]q=([^&]+)"),
)


class _GoogleSearchCleaner(UrlCleaner):
    id = "google_search"
    category = CleanerCategory.SEARCH_ENGINES

    def matches(self, url: str) -> bool:
        if not CleanerUtils.host_matches(url, _DOMAINS):
            return False
        lower = url.lower()
        return "/url?" in lower or "/search?" in lower

    def clean(self, url: str) -> str:
        if "/url?" in url:
            redirected = self._extract_redirect(url)
            if redirected:
                return redirected
        if "?" not in url:
            return url

        def decide(key: str, pair: str) -> str | None:
            if key in _PRESERVE:
                return pair
            if key in _TRACKING:
                return None
            return None
        return CleanerUtils.filter_query(url, decide)

    @staticmethod
    def _extract_redirect(url: str) -> str | None:
        for pat in _REDIRECT_PATTERNS:
            m = pat.search(url)
            if not m:
                continue
            try:
                decoded = urllib.parse.unquote(m.group(1))
            except Exception:
                continue
            if decoded.startswith("http://") or decoded.startswith("https://"):
                return decoded
        return None


GoogleSearchCleaner = _GoogleSearchCleaner()
