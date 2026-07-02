"""Amazon cleaner — extracts `/dp/<ASIN>` canonical form when possible."""
from __future__ import annotations

import re

from ..base import CleanerCategory, CleanerUtils, UrlCleaner

_DOMAINS = (
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr",
    "amazon.it", "amazon.es", "amazon.ca", "amazon.co.jp",
    "amazon.in", "amazon.com.br", "amazon.com.mx", "amazon.com.au",
    "amzn.to", "amzn.eu", "amzn.asia",
)

_TRACKING = frozenset({
    "tag", "linkCode", "linkId", "camp", "creative",
    "creativeASIN", "ref_", "ref", "refRID", "ie",
    "pf_rd_m", "pf_rd_s", "pf_rd_r", "pf_rd_t", "pf_rd_p", "pf_rd_i",
    "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pf_rd_sg",
    "pd_rd_sg", "pd_dcr", "pd_rd_w-k", "pd_rd_r-k",
    "qid", "rank", "spIA", "spLa", "suggestionType",
    "sprefix", "crid", "cv_ct_cx", "cv_ct_id", "cv_ct_pg",
    "share", "share_at", "socialMediaReferral", "referer",
    "ms3_c", "spLM", "spPD", "spIAC",
    "smid", "ascsubtag", "tag_id", "sa-no-redirect",
    "pldnSite", "th", "psc", "dchild", "almBrandId",
    "navLanguage", "rnid", "rh", "srs", "starsLeft",
    "qsid", "sr", "sres", "__mk_de_DE", "__mk_en_US",
    "sessionId", "sqid", "colid", "coliid", "ubid",
    "visitId", "asc_campaign", "asc_source", "asc_refurl",
    "feature", "variant", "experiment", "treatment",
    "bucket", "version", "isTest", "qualifier",
    "_encoding", "bbn", "dc", "dcm", "field-lbr_brands_browse-bin",
    "fst", "lo", "me", "pf",
    "deviceType", "deviceVersion", "appVersion", "platform",
    "isAndroid", "isIOS", "isMobile", "isTablet",
    "carId", "cartInitiateId", "fromAnywhere", "sbbutton",
    "ascsess", "asc_contentid", "asc_item", "asc_topic",
    "associateTag", "marketplaceID", "maas",
    "adId", "ad-id", "campaign", "adgrpid",
    "primeCampaignId", "primeExpirationDate", "primeStatus",
    "benefitId", "benefitOptimizationId", "subscriptionId",
    "wl_id", "registry", "registryId",
    "registryType", "weblab-wl", "wl-id",
    "encoding", "node", "nodeId", "field-keywords",
    "url", "path", "hidden-keywords", "fap", "fie",
    "redirect", "redirectASIN", "sspa", "spNs",
    "t", "marketplaceId", "merchant", "queueName",
    "rdc", "rdm", "rdl", "sourcecustomerorglistid",
    "sourcecustomerorglistitemid", "sz", "idx",
})

_PRESERVE = frozenset({
    "keywords", "k", "i", "rh", "s", "page",
    "node", "field-keywords", "field-brand",
    "field-price-range", "field-availability",
    "sort", "lo", "fs",
})

# Order matters: `/dp/<asin>` is the canonical form; falls back to looser patterns.
_ASIN_PATTERNS = [
    re.compile(r"/dp/([A-Z0-9]{10})"),
    re.compile(r"/gp/product/([A-Z0-9]{10})"),
    re.compile(r"/exec/obidos/ASIN/([A-Z0-9]{10})"),
    re.compile(r"/([A-Z0-9]{10})(?:/|\?|$)"),
]

_DOMAIN_RE = {
    domain: re.compile(rf"((?:www\.|smile\.)?{re.escape(domain)})", re.IGNORECASE)
    for domain in _DOMAINS
}


class _AmazonCleaner(UrlCleaner):
    id = "amazon"
    category = CleanerCategory.E_COMMERCE

    def matches(self, url: str) -> bool:
        return CleanerUtils.host_matches(url, _DOMAINS)

    def clean(self, url: str) -> str:
        asin = self._extract_asin(url)
        if asin:
            host = self._extract_host(url) or "www.amazon.com"
            return f"https://{host}/dp/{asin}"
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
    def _extract_asin(url: str) -> str | None:
        for pat in _ASIN_PATTERNS:
            m = pat.search(url)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _extract_host(url: str) -> str | None:
        lower = url.lower()
        for domain in _DOMAINS:
            if domain in lower:
                m = _DOMAIN_RE[domain].search(url)
                if m:
                    return m.group(1).lower()
        return None


AmazonCleaner = _AmazonCleaner()
