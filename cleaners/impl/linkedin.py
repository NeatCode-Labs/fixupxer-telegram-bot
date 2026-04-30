"""LinkedIn cleaner — keeps `f_*` filter params, strips lnkd.in queries."""
from __future__ import annotations

from ..base import CleanerCategory, UrlCleaner

_TRACKING = frozenset({
    "trk", "trkInfo", "trkEmail", "li_theme", "li_ft",
    "li_mc", "li_tc", "li_uuid", "li_at", "li_rm",
    "share", "src", "veh", "trackingId", "refId",
    "lipi", "licu", "lici", "lict", "lics",
    "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "mcid", "msgConversationId",
    "sessionId", "requestId", "contextId", "csrfToken",
    "pageKey", "sessionRedirect", "fromSignIn",
    "position", "pageNum", "secureUrl", "startTask",
    "submissionId", "upsellOrderOrigin", "fromEmail",
    "midToken", "midSig", "fromSuggestionID", "suggestedToFollow",
    "updateEntityUrn", "originTrackingId",
    "msgOverlay", "messageThreadUrn", "threadUrn",
    "conversationUrn", "creatorUrn", "entityUrn",
    "alternateChannel", "alertAction", "savedSearchId",
    "searchId", "searchRequestId", "currentJobId",
    "fromJobAlertEmail", "fromJobAlertMail", "jobAlertAction",
    "appId", "appStore", "mobileApp", "isFromMobileJob",
    "isFromMobile", "deviceType", "os", "trk_ref",
    "invitation", "sharedKey", "sig", "invitationId",
    "invitationType", "connectionOf", "senderIdentityHint",
    "groupId", "companyId", "organizationId", "followerId",
    "memberIdentity", "moduleKey", "detailOrigin",
    "articleId", "commentUrn", "dashCommentUrn", "replyUrn",
    "parentCommentUrn", "articleSortOrder", "sectionName",
    "sp", "imp", "campaign", "account", "creative",
    "sendTime", "serveTime", "displayTime", "sponsored",
    "success", "u", "e", "courseClaim", "learningHistory",
    "pk", "pv", "biz", "goback", "report", "urlhash",
    "eBP", "rs", "key", "pivot", "redirSrc", "spSrc",
})

_PRESERVE = frozenset({
    "keywords", "origin", "q", "start", "count",
    "filters", "sortBy", "facet",
    "geoUrn", "network", "schoolFilter", "companySize",
    "datePosted", "jobType", "location",
    "redirectUrl", "response_type", "client_id", "state", "scope",
})


class _LinkedInCleaner(UrlCleaner):
    id = "linkedin"
    category = CleanerCategory.SOCIAL_MEDIA

    def matches(self, url: str) -> bool:
        lower = url.lower()
        return "linkedin.com" in lower or "lnkd.in" in lower

    def clean(self, url: str) -> str:
        if "lnkd.in" in url.lower():
            q = url.find("?")
            return url if q == -1 else url[:q]
        if "?" not in url:
            return url
        from ..base import CleanerUtils

        def decide(key: str, pair: str) -> str | None:
            if key in _PRESERVE:
                return pair
            if key.startswith("f_"):
                return pair  # f_* filter params (per app)
            if key in _TRACKING:
                return None
            return None
        return CleanerUtils.filter_query(url, decide)


LinkedInCleaner = _LinkedInCleaner()
