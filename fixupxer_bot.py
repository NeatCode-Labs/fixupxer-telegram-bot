#!/usr/bin/env python3
import asyncio
import collections
import contextlib
import json
import logging
import os
import re
import sqlite3
import time
import urllib.parse
from html import escape as html_escape

from telegram import Update
from telegram.error import (
    BadRequest,
    Conflict,
    Forbidden,
    NetworkError,
    TelegramError,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import cleaners as cleaner_engine

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=os.environ.get("FIXUPXER_LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger(__name__)

# Soft imports for optional health-check stack. If httpx or cachetools is
# missing, the bot still runs — embed verification is silently disabled and
# the original (string-only) Instagram conversion path is used instead.
try:
    import httpx as _httpx
except ImportError:
    _httpx = None

try:
    import cachetools as _cachetools
except ImportError:
    _cachetools = None


def _parse_int_csv(raw: str | None, label: str) -> list[int]:
    """Parse a comma-separated list of integers from an env var.

    Whitespace around tokens is trimmed; empty tokens are skipped; non-integer
    tokens emit a warning and are skipped (start-up does not abort).
    """
    if not raw:
        return []
    out: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            logger.warning("Invalid %s id ignored: %r", label, token)
    return out


def _parse_str_csv(raw: str | None, default: tuple[str, ...]) -> list[str]:
    """Parse a comma-separated list of strings; falls back to default if empty."""
    if not raw or not raw.strip():
        return list(default)
    out = [token.strip() for token in raw.split(",") if token.strip()]
    return out or list(default)


# In-memory read-cache for /delete authorisation. SQLite (delete_tokens
# table) is the source of truth; this dict avoids a DB hit on every
# /delete. Bounded LRU prevents unbounded growth on long-running deploys.
if _cachetools is not None:
    user_message_map: dict = _cachetools.LRUCache(maxsize=5000)
else:
    user_message_map = {}

BOT_ADMINS: list[int] = _parse_int_csv(os.environ.get("FIXUPXER_ADMINS"), "FIXUPXER_ADMINS")

# When True, init_db / track_* / /stats are no-ops (per README).
STATS_DISABLED: bool = os.environ.get("FIXUPXER_DISABLE_STATS") == "1"

# ---- Instagram proxy configuration --------------------------------------
# Default order mirrors the Android app v1.6.0 roster: toinstagram.com and
# adamlikes.men (primaries — full OG meta tags: media + post/reel title &
# description), then instagram7.com and kkinstagram.com (backups).
# _ig_probe accepts both styles (full og:image/og:video HTML and image/* or
# video/* CDN redirects).
# All proxies are addressed on the bare host (no `www.` prefix). Adamlikes
# requires it (no DNS record for `www.`), and the others accept either form
# — so the consistent bare-host policy keeps the URL shape uniform.
# _HISTORICAL_IG_HOSTS lists hosts the bot recognises as Instagram so pasted
# URLs on those (dead/passthrough) proxies still get cleaned and re-hosted
# onto an active proxy.
_DEFAULT_IG_PROXIES = (
    "toinstagram.com", "adamlikes.men", "instagram7.com", "kkinstagram.com",
)
_HISTORICAL_IG_HOSTS = (
    "eeinstagram.com",
    "ddinstagram.com",
)
IG_PROXY_ORDER: list[str] = _parse_str_csv(
    os.environ.get("FIXUPXER_IG_PROXY_ORDER"), _DEFAULT_IG_PROXIES,
)
IG_HEALTH_TTL_SECONDS: int = int(os.environ.get("FIXUPXER_IG_HEALTH_TTL_SECONDS", "600"))
IG_PROBE_INTERVAL_SECONDS: int = int(
    os.environ.get("FIXUPXER_IG_PROBE_INTERVAL_SECONDS", "120")
)
IG_VERIFY_EMBED: bool = os.environ.get("FIXUPXER_IG_VERIFY_EMBED", "1") == "1"
IG_CACHE_BUST: bool = os.environ.get("FIXUPXER_IG_CACHE_BUST") == "1"

# Disable embed verification if dependencies are missing — log once at startup.
if IG_VERIFY_EMBED and _httpx is None:
    logger.warning(
        "httpx is not installed; FIXUPXER_IG_VERIFY_EMBED disabled. "
        "Install with: pip install httpx"
    )
    IG_VERIFY_EMBED = False
if IG_VERIFY_EMBED and _cachetools is None:
    logger.warning(
        "cachetools is not installed; FIXUPXER_IG_VERIFY_EMBED disabled. "
        "Install with: pip install cachetools"
    )
    IG_VERIFY_EMBED = False

_IG_HTTP_TIMEOUT: float = 3.0
_IG_USER_AGENT: str = "TelegramBot (like TwitterBot)"
_IG_MAX_BYTES: int = 65536
# Path used by the background probe to keep proxy health current. Must be a
# real, public post that all configured proxies can serve. Configurable via
# env var so operators can swap it if the chosen post is ever deleted.
_IG_BG_PROBE_PATH: str = os.environ.get(
    "FIXUPXER_IG_BG_PROBE_PATH", "/p/DXKIQo0CPjX/",
)
_IG_CIRCUIT_OPEN_SECONDS: int = 300
_IG_CIRCUIT_FAIL_THRESHOLD: int = 5
_IG_CIRCUIT_FAIL_WINDOW: int = 60

# Message divider used in templates
DIVIDER = '───────────────────────'

# Supported platforms enumeration
PLATFORM_X = 'x'
PLATFORM_INSTAGRAM = 'instagram'
PLATFORM_FACEBOOK = 'facebook'
PLATFORM_TIKTOK = 'tiktok'
# Used for any host that the cleaner engine touched but for which we don't
# do a domain rewrite (YouTube, Reddit, Amazon, Substack, …).
PLATFORM_OTHER = 'other'

# ---- TikTok proxy configuration (mirrors app v1.7.0 Constants.kt) --------
# Primary proxies embed video + description; backups are fallbacks. Legacy
# proxies are recognised only so pasted URLs on them get migrated to the
# active proxy. Unlike Instagram, subdomain prefixes (vm./vt./m./www.) are
# preserved on rewrite — short-link resolution happens on the same prefix.
_TIKTOK_PROXY_DOMAINS = ("tnktok.com", "tfxktok.com", "tiktokez.com", "kktiktok.com")
_TIKTOK_LEGACY_PROXIES = ("vxtiktok.com", "tiktxk.com")
TIKTOK_PROXY_ORDER: list[str] = _parse_str_csv(
    os.environ.get("FIXUPXER_TIKTOK_PROXY_ORDER"), _TIKTOK_PROXY_DOMAINS,
)
# TikTok embed verification reuses the Instagram probe machinery. Defaults
# to the FIXUPXER_IG_VERIFY_EMBED setting so one env var disables both
# (tests/CI only set the IG flag).
TIKTOK_VERIFY_EMBED: bool = os.environ.get(
    "FIXUPXER_TIKTOK_VERIFY_EMBED",
    os.environ.get("FIXUPXER_IG_VERIFY_EMBED", "1"),
) == "1"
if TIKTOK_VERIFY_EMBED and (_httpx is None or _cachetools is None):
    TIKTOK_VERIFY_EMBED = False  # same dependency requirement as the IG check
# Background-probe path: must be a real, public video every proxy can serve.
_TT_BG_PROBE_PATH: str = os.environ.get(
    "FIXUPXER_TIKTOK_BG_PROBE_PATH", "/@cwknix/video/7529264180000509202",
)

# Grab every http(s) run of non-space characters; trailing prose punctuation
# ("see https://x.com/foo.") is stripped afterwards by _trim_url_trail.
URL_PATTERN = re.compile(r'https?://\S+')

# Characters that must be stripped from the end of a captured URL because
# they almost always belong to surrounding prose, not the URL itself.
_URL_TRAIL_STRIP = '.,;:!?\'")]}>'


def _trim_url_trail(url: str) -> str:
    """Strip trailing prose punctuation from a captured URL.

    Closing brackets/parens/quotes/dots etc. are stripped, but balanced
    closing parens are kept (e.g. Wikipedia URLs).
    """
    while url and url[-1] in _URL_TRAIL_STRIP:
        if url[-1] == ')' and url.count('(') > url.count(')') - 1:
            break
        url = url[:-1]
    return url

# ------------------------ DATABASE LAYER -----------------------------

def _db_path() -> str:
    # FIXUPXER_DB_PATH lets Docker/compose mount a volume at e.g. /data/bot_stats.db
    # without baking that path into the image.
    override = os.environ.get("FIXUPXER_DB_PATH")
    if override:
        return override
    return os.path.join(os.path.dirname(__file__), "bot_stats.db")


def _db_connect():
    """Open a fresh SQLite connection with WAL mode and foreign keys.

    A fresh connection per call keeps the implementation simple and avoids
    threading hazards when callers run via asyncio.to_thread. The actual cost
    (sub-millisecond on local fs) is dwarfed by the surrounding I/O.
    """
    conn = sqlite3.connect(_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    chat_title TEXT,
    chat_type TEXT,
    member_count INTEGER DEFAULT 0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    chat_id INTEGER,
    original_url TEXT,
    converted_url TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (chat_id) REFERENCES chats (chat_id)
);
CREATE TABLE IF NOT EXISTS delete_tokens (
    bot_message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ts INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    PRIMARY KEY (chat_id, bot_message_id)
);
CREATE INDEX IF NOT EXISTS idx_delete_tokens_ts ON delete_tokens(ts);
"""


def init_db() -> None:
    """Create / migrate the SQLite schema (no-op if FIXUPXER_DISABLE_STATS)."""
    if STATS_DISABLED:
        logger.info("FIXUPXER_DISABLE_STATS=1 — skipping database initialization")
        return
    conn = _db_connect()
    try:
        conn.executescript(_DB_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    logger.info("Database initialised at %s", _db_path())


def _track_user_sync(user_id, username, first_name, last_name) -> None:
    conn = _db_connect()
    try:
        conn.execute(
            "INSERT INTO users (user_id, username, first_name, last_name) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "  username = excluded.username, "
            "  first_name = excluded.first_name, "
            "  last_name = excluded.last_name, "
            "  last_active = CURRENT_TIMESTAMP",
            (user_id, username, first_name, last_name),
        )
        conn.commit()
    finally:
        conn.close()


def _track_chat_sync(chat_id, chat_title, chat_type) -> None:
    conn = _db_connect()
    try:
        conn.execute(
            "INSERT INTO chats (chat_id, chat_title, chat_type) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET "
            "  chat_title = excluded.chat_title, "
            "  last_active = CURRENT_TIMESTAMP",
            (chat_id, chat_title, chat_type),
        )
        conn.commit()
    finally:
        conn.close()


def _track_conversion_sync(user_id, chat_id, original_url, converted_url) -> None:
    conn = _db_connect()
    try:
        conn.execute(
            "INSERT INTO conversions (user_id, chat_id, original_url, converted_url) "
            "VALUES (?, ?, ?, ?)",
            (user_id, chat_id, original_url, converted_url),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_token_save_sync(bot_msg_id, chat_id, user_id) -> None:
    conn = _db_connect()
    try:
        # Opportunistic cleanup: drop tokens older than 24 hours.
        conn.execute(
            "DELETE FROM delete_tokens WHERE ts < strftime('%s','now') - 86400"
        )
        conn.execute(
            "INSERT OR REPLACE INTO delete_tokens (bot_message_id, chat_id, user_id) "
            "VALUES (?, ?, ?)",
            (bot_msg_id, chat_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_token_lookup_sync(chat_id, bot_msg_id) -> int | None:
    conn = _db_connect()
    try:
        cursor = conn.execute(
            "SELECT user_id FROM delete_tokens "
            "WHERE chat_id = ? AND bot_message_id = ?",
            (chat_id, bot_msg_id),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _delete_token_remove_sync(chat_id, bot_msg_id) -> None:
    conn = _db_connect()
    try:
        conn.execute(
            "DELETE FROM delete_tokens WHERE chat_id = ? AND bot_message_id = ?",
            (chat_id, bot_msg_id),
        )
        conn.commit()
    finally:
        conn.close()


async def track_user(user) -> None:
    if STATS_DISABLED or not user:
        return
    await asyncio.to_thread(
        _track_user_sync, user.id, user.username, user.first_name, user.last_name,
    )


async def track_chat(chat) -> None:
    if STATS_DISABLED or not chat:
        return
    await asyncio.to_thread(_track_chat_sync, chat.id, chat.title, chat.type)


async def track_conversion(user_id, chat_id, original_url, converted_url) -> None:
    if STATS_DISABLED:
        return
    await asyncio.to_thread(
        _track_conversion_sync, user_id, chat_id, original_url, converted_url,
    )


async def _save_delete_token(bot_msg_id: int, chat_id: int, user_id: int) -> None:
    if STATS_DISABLED:
        return  # Token persistence requires the DB; in-memory map is the only record.
    await asyncio.to_thread(_delete_token_save_sync, bot_msg_id, chat_id, user_id)


async def _lookup_delete_token(chat_id: int, bot_msg_id: int) -> int | None:
    if STATS_DISABLED:
        return None
    return await asyncio.to_thread(_delete_token_lookup_sync, chat_id, bot_msg_id)


async def _remove_delete_token(chat_id: int, bot_msg_id: int) -> None:
    if STATS_DISABLED:
        return
    await asyncio.to_thread(_delete_token_remove_sync, chat_id, bot_msg_id)

# ------------------------ PROXY EMBED HEALTH -------------------------

# All runtime state below is single-event-loop: no thread synchronization
# needed because cachetools mutations occur between awaits, never inside
# preemptive threads.
_ig_proxy_override: str | None = None  # set by /setproxy <domain>; None means auto

# httpx async client shared by all probes; lazily created so unit tests
# don't open sockets.
_probe_http_client: "object | None" = None

# OG meta tag matcher (handles both attribute orderings: property first OR content first).
_OG_META_PROP_FIRST = re.compile(
    r"""<meta[^>]+?property=["'](og:(?:image|video)(?::url|:secure_url)?)["'][^>]*?content=["']([^"']+)["']""",
    re.IGNORECASE,
)
_OG_META_CONTENT_FIRST = re.compile(
    r"""<meta[^>]+?content=["']([^"']+)["'][^>]*?property=["'](og:(?:image|video)(?::url|:secure_url)?)["']""",
    re.IGNORECASE,
)

# Video-specific extractors: used to double-check that a page claiming a video
# embed actually links to playable video content (see _media_is_video).
_OG_VIDEO_PROP_FIRST = re.compile(
    r"""<meta[^>]+?(?:property|name)=["'](?:og:video(?::url|:secure_url)?|twitter:player:stream)["'][^>]*?content=["']([^"']+)["']""",
    re.IGNORECASE,
)
_OG_VIDEO_CONTENT_FIRST = re.compile(
    r"""<meta[^>]+?content=["']([^"']+)["'][^>]*?(?:property|name)=["'](?:og:video(?::url|:secure_url)?|twitter:player:stream)["']""",
    re.IGNORECASE,
)


def _log_evt(evt: str, **fields) -> None:
    """Structured-log helper (single-line JSON, easy to grep)."""
    try:
        logger.info("%s", json.dumps({"evt": evt, **fields}, default=str))
    except Exception:  # noqa: BLE001
        logger.info("%s %r", evt, fields)


async def _get_probe_http_client():
    global _probe_http_client
    if _probe_http_client is not None:
        return _probe_http_client
    if _httpx is None:
        return None
    _probe_http_client = _httpx.AsyncClient(
        timeout=_IG_HTTP_TIMEOUT,
        follow_redirects=True,
        max_redirects=3,
        headers={"User-Agent": _IG_USER_AGENT},
    )
    return _probe_http_client


def _has_og_media(text: str) -> str | None:
    """Return the first og:image / og:video URL found, or None."""
    for m in _OG_META_PROP_FIRST.finditer(text):
        return m.group(2)
    for m in _OG_META_CONTENT_FIRST.finditer(text):
        return m.group(1)
    return None


def _og_video_url(text: str) -> str | None:
    """Return the og:video / twitter:player:stream URL if the page declares one."""
    for m in _OG_VIDEO_PROP_FIRST.finditer(text):
        return m.group(1)
    for m in _OG_VIDEO_CONTENT_FIRST.finditer(text):
        return m.group(1)
    return None


async def _media_is_video(client, media_url: str) -> bool:
    """GET the declared video URL and verify it really serves ``video/*``.

    Catches half-dead proxies whose og:video endpoint redirects to a JPEG
    cover frame (Telegram then renders a file attachment instead of a video
    player) or errors out. Reads headers only — the body is never downloaded.
    """
    try:
        async with client.stream(
            "GET", media_url, headers={"Range": "bytes=0-1023"},
        ) as response:
            if response.status_code not in (200, 206):
                return False
            ct = response.headers.get("content-type", "").lower()
            return ct.startswith("video/")
    except Exception:  # noqa: BLE001 - any failure = endpoint can't serve video
        return False


class _ProxyHealthChecker:
    """Embed-health state for one platform's proxy roster.

    Bundles the probe result cache (TTL), per-proxy circuit breakers, a 1h
    event log and thundering-herd dedup. One instance per platform (IG,
    TikTok) so their health states never interfere.
    """

    def __init__(self, name: str, ttl_seconds: int) -> None:
        self._name = name  # used in log lines and probe-error events
        if _cachetools is not None:
            self._url_health = _cachetools.TTLCache(maxsize=2000, ttl=ttl_seconds)
        else:
            self._url_health = {}  # fallback: only used when verify disabled
        # Per-proxy circuit state: {proxy: {state, opened_ts, fails: list[ts]}}
        self._circuit: dict[str, dict] = {}
        # Per-(host, path) inflight probe Events for thundering-herd dedup.
        self._inflight: dict[tuple[str, str], asyncio.Event] = {}
        # Per-proxy event log for /setproxy status (1h window).
        self._events: dict[str, collections.deque] = {}

    # ---- circuit breaker ----

    def circuit_get(self, proxy: str) -> dict:
        return self._circuit.setdefault(
            proxy, {"state": "closed", "opened_ts": 0.0, "fails": []}
        )

    def circuit_record_fail(self, proxy: str) -> None:
        """Record a failure; open the circuit if 5 fails happen within 60 s."""
        now = time.time()
        c = self.circuit_get(proxy)
        c["fails"] = [t for t in c["fails"] if now - t <= _IG_CIRCUIT_FAIL_WINDOW]
        c["fails"].append(now)
        if len(c["fails"]) >= _IG_CIRCUIT_FAIL_THRESHOLD and c["state"] != "open":
            c["state"] = "open"
            c["opened_ts"] = now
            c["fails"] = []
            logger.warning(
                "%s proxy %s circuit OPEN (>=5 fails in 60s)", self._name, proxy,
            )

    def circuit_record_ok(self, proxy: str) -> None:
        c = self.circuit_get(proxy)
        if c["state"] != "closed":
            logger.info("%s proxy %s circuit CLOSED (recovered)", self._name, proxy)
        c["state"] = "closed"
        c["opened_ts"] = 0.0
        c["fails"] = []

    def circuit_should_skip(self, proxy: str) -> bool:
        """Return True if the breaker is open and the cool-down hasn't elapsed."""
        c = self.circuit_get(proxy)
        if c["state"] != "open":
            return False
        if time.time() - c["opened_ts"] >= _IG_CIRCUIT_OPEN_SECONDS:
            # Half-open: allow next probe to decide.
            c["state"] = "half_open"
            return False
        return True

    # ---- event log ----

    def record_event(self, proxy: str, evt: str) -> None:
        now = time.time()
        dq = self._events.setdefault(proxy, collections.deque(maxlen=2000))
        dq.append((now, evt))
        while dq and now - dq[0][0] > 3600:
            dq.popleft()

    def event_counts_1h(self, proxy: str) -> tuple[int, int]:
        now = time.time()
        dq = self._events.get(proxy)
        if not dq:
            return 0, 0
        ok = fail = 0
        for ts, evt in dq:
            if now - ts > 3600:
                continue
            if evt == "ok":
                ok += 1
            else:
                fail += 1
        return ok, fail

    # ---- probe cache ----

    def _cache_get(self, cache_key: tuple[str, str]) -> dict | None:
        if _cachetools is None:
            return None
        return self._url_health.get(cache_key)

    def _cache_set(
        self,
        cache_key: tuple[str, str],
        passed: bool,
        og_url: str | None,
        final_url: str | None,
    ) -> None:
        if _cachetools is None:
            return
        self._url_health[cache_key] = {
            "passed": passed,
            "og_url": og_url,
            "final_url": final_url,
        }

    # ---- probe ----

    async def probe(
        self, proxy: str, path: str, host: str | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Probe a proxy for embed availability at ``path``.

        ``host`` is the actual hostname to request (defaults to ``proxy``);
        TikTok passes e.g. ``vm.tnktok.com`` while the circuit breaker stays
        keyed on the bare proxy. Returns (passed, og_media_url_or_None,
        final_url_after_redirects_or_None). The final URL lets the caller
        detect when a proxy 302s away to the origin site so it can prefer a
        proxy that serves the embed itself. Result is cached for the checker's
        TTL. Concurrent callers for the same key share the probe via an
        asyncio.Event (thundering-herd dedup).
        """
        host = host or proxy
        cache_key = (host, path)

        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached["passed"], cached.get("og_url"), cached.get("final_url")

        inflight = self._inflight.get(cache_key)
        if inflight is not None:
            await inflight.wait()
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached["passed"], cached.get("og_url"), cached.get("final_url")
            return False, None, None

        event = asyncio.Event()
        self._inflight[cache_key] = event
        try:
            url = f"https://{host}{path}"
            passed = False
            og_url: str | None = None
            final_url: str | None = None
            client = await _get_probe_http_client()
            if client is None:
                return False, None, None
            try:
                response = await client.get(url)
                final_url = str(response.url)
                if response.status_code in (200, 206):
                    ct = response.headers.get("content-type", "").lower()
                    if ct.startswith("image/") or ct.startswith("video/"):
                        # Proxy 302'd to raw CDN media (e.g. instagram7.com →
                        # scontent.cdninstagram.com/X.jpg). Telegram still
                        # renders an image preview when crawling the proxy URL,
                        # so treat this as a successful embed. We pin final_url
                        # back to the proxy URL so the caller's served_by_proxy
                        # check keeps the user-facing URL on the proxy (avoiding
                        # leaking the signed CDN URL with a short TTL).
                        og_url = final_url
                        final_url = url
                        passed = True
                    else:
                        text = response.text[:_IG_MAX_BYTES]
                        og_url = _has_og_media(text)
                        passed = og_url is not None
                        # When the proxy itself serves a page claiming a video
                        # embed, verify the video endpoint actually returns
                        # video/* — half-dead proxies redirect it to a JPEG
                        # cover frame, which Telegram renders as a file
                        # attachment. (Skipped when the page came from a
                        # redirect to the origin site: those candidates are
                        # already last-resort fallbacks.)
                        if passed and response.url.host == host:
                            video_url = _og_video_url(text)
                            if video_url is not None:
                                resolved = urllib.parse.urljoin(
                                    str(response.url), video_url,
                                )
                                if not await _media_is_video(client, resolved):
                                    passed = False
                                    og_url = None
                                    _log_evt(
                                        f"{self._name}_probe_bad_video",
                                        proxy=proxy, path=path, video=resolved,
                                    )
            except Exception as e:  # noqa: BLE001 - any failure = proxy didn't serve
                _log_evt(
                    f"{self._name}_probe_error", proxy=proxy, path=path, error=str(e),
                )

            if passed:
                self.circuit_record_ok(proxy)
                self.record_event(proxy, "ok")
            else:
                self.circuit_record_fail(proxy)
                self.record_event(proxy, "fail")

            self._cache_set(cache_key, passed, og_url, final_url)
            return passed, og_url, final_url
        finally:
            event.set()
            self._inflight.pop(cache_key, None)


_IG_HEALTH = _ProxyHealthChecker("ig", IG_HEALTH_TTL_SECONDS)
_TT_HEALTH = _ProxyHealthChecker("tiktok", IG_HEALTH_TTL_SECONDS)


# Module-level wrappers keep call sites (and test monkeypatching) simple.
async def _ig_probe(proxy: str, path: str) -> tuple[bool, str | None, str | None]:
    return await _IG_HEALTH.probe(proxy, path)


async def _tt_probe(
    proxy: str, path: str, host: str | None = None,
) -> tuple[bool, str | None, str | None]:
    return await _TT_HEALTH.probe(proxy, path, host=host)


def _instagram_url_with_proxy(clean_url: str, proxy: str) -> str:
    """Rewrite an IG URL's netloc to the chosen proxy via urlunparse.

    Uses urlunparse (not str.replace) so that the rewrite is robust against
    mixed-case input like https://WWW.Instagram.com/... . The netloc is set
    to the bare proxy host (any leading `www.` in the configured proxy is
    stripped) so the user-facing URL is uniform across all proxies.
    """
    parsed = urllib.parse.urlparse(clean_url)
    netloc = proxy[4:] if proxy.startswith("www.") else proxy
    new_url = urllib.parse.urlunparse((
        parsed.scheme or "https",
        netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    if IG_CACHE_BUST:
        # Hour-bucketed value: changes once per hour without breaking proxy parsing.
        bust = int(time.time()) // 3600
        sep = "&" if parsed.query else "?"
        # Insert before fragment if present.
        if parsed.fragment:
            base, frag = new_url.rsplit("#", 1)
            new_url = f"{base}{sep}fixupxer_v={bust}#{frag}"
        else:
            new_url = f"{new_url}{sep}fixupxer_v={bust}"
    return new_url


# ------------------------ URL HELPERS ----------------------------

# 1h TTL, 10k entries — matches CleanerCache.kt sizing.
if _cachetools is not None:
    _CLEAN_CACHE: "_cachetools.TTLCache" = _cachetools.TTLCache(maxsize=10_000, ttl=3600)
else:
    _CLEAN_CACHE = {}


def _cleaner_cache_get(url: str) -> str | None:
    return _CLEAN_CACHE.get(url) if _cachetools is not None else None


def _cleaner_cache_set(url: str, cleaned: str) -> None:
    if _cachetools is None:
        return
    _CLEAN_CACHE[url] = cleaned


# Wire the bot's cache callbacks into the cleaner engine's default service.
cleaner_engine._DEFAULT_SERVICE = cleaner_engine.CleanerService(
    cleaner_engine.DEFAULT_REGISTRY,
    cache_get=_cleaner_cache_get,
    cache_set=_cleaner_cache_set,
)


def _clean_query(url: str) -> str:
    """Run the modular cleaning engine (preprocess + multi-pass deep clean)."""
    return cleaner_engine.deep_clean(url)

def _convert_x(url: str):
    """Return (fixed_url, clean_url) for X / Twitter / fixupx / fxtwitter / vxtwitter links.

    Behaviour mirrors the Android app's TwitterCleaner: vxtwitter (and the
    other proxy domains) are recognised so tracking gets cleaned, but their
    domain is left intact — only twitter.com / x.com get rewritten to fixupx.
    """
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()

    clean_original = _clean_query(url)

    # Already a Twitter-family proxy domain → just cleaned, no rewrite.
    # clean_url=None signals to _build_message that there is no separate
    # "fallback" link to render (avoids a duplicate row pointing at the same URL).
    if any(host == domain or domain.endswith("." + host)
           for host in ("fixupx.com", "fxtwitter.com", "vxtwitter.com")):
        return clean_original, None

    parsed_clean = urllib.parse.urlparse(clean_original)

    def _swap_netloc(new_host: str) -> str:
        return urllib.parse.urlunparse((
            parsed_clean.scheme or "https",
            new_host,
            parsed_clean.path,
            parsed_clean.params,
            parsed_clean.query,
            parsed_clean.fragment,
        ))

    if domain == "x.com" or domain.endswith(".x.com"):
        return _swap_netloc("fixupx.com"), clean_original
    if domain == "twitter.com" or domain.endswith(".twitter.com"):
        return _swap_netloc("fxtwitter.com"), clean_original

    return clean_original, clean_original  # defensive fallback

async def _convert_instagram_async(url: str) -> tuple[str | None, str]:
    """Convert an Instagram URL using the healthiest available proxy.

    Returns (fixed_url, clean_url). If health checks are enabled and *all*
    candidate proxies fail to serve an OG embed, returns (None, clean_url) —
    the all-fail signal honoured by process_message (log + skip; do not send
    a replacement message; do not delete the original).
    """
    clean_original = _clean_query(url)
    parsed = urllib.parse.urlparse(clean_original)
    domain = parsed.netloc.lower()
    path = parsed.path or "/"

    def _strip_ig_subdomain(host: str) -> str:
        """Drop a leading ``www.`` so the comparison matches IG_PROXY_ORDER tokens."""
        return host[4:] if host.startswith("www.") else host

    bare_host = _strip_ig_subdomain(domain)

    # Already on an *active* proxy — normalise via _instagram_url_with_proxy
    # so a pasted `www.toinstagram.com/...` (or any other proxy with www.)
    # becomes the canonical bare-host form we always emit. If the cleaned URL
    # was already canonical, the rewrite is a no-op and we still return it
    # so the caller short-circuits to the 2-link layout.
    matched_proxy = next(
        (p for p in IG_PROXY_ORDER if bare_host == p or bare_host.endswith("." + p)),
        None,
    )
    if matched_proxy is not None:
        canonical = _instagram_url_with_proxy(clean_original, matched_proxy)
        return canonical, None

    # On a HISTORICAL proxy (kk/ee/dd) that's no longer in IG_PROXY_ORDER →
    # re-host onto an active proxy, fall through to probing. First normalise
    # the URL back to instagram.com so the probe path is constructed cleanly.
    if any(bare_host == p or bare_host.endswith("." + p) for p in _HISTORICAL_IG_HOSTS):
        clean_original = urllib.parse.urlunparse((
            parsed.scheme or "https",
            "www.instagram.com",
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
        parsed = urllib.parse.urlparse(clean_original)
        domain = parsed.netloc.lower()
        path = parsed.path or "/"

    # Override forces a single proxy (admin escape hatch) — same all-fail
    # policy applies if it doesn't serve.
    if _ig_proxy_override is not None:
        candidates: list[str] = [_ig_proxy_override]
    else:
        candidates = [p for p in IG_PROXY_ORDER if not _IG_HEALTH.circuit_should_skip(p)]
        if not candidates:
            # Every breaker open — try them all in half-open state.
            candidates = list(IG_PROXY_ORDER)

    if not IG_VERIFY_EMBED:
        # Health checks disabled (deps missing or env opt-out).
        proxy = candidates[0] if candidates else IG_PROXY_ORDER[0]
        fixed = _instagram_url_with_proxy(clean_original, proxy)
        # When fixed equals clean_original the rewrite was a no-op (already on
        # the chosen proxy); signal that with clean_url=None so _build_message
        # collapses to the 2-link layout.
        return fixed, (None if fixed == clean_original else clean_original)

    last_error: str | None = None
    # A proxy that "passed" only via a redirect back to instagram.com is a
    # weak result: Telegram does not render embeds for plain instagram.com
    # links, so prefer any proxy that serves the embed itself and keep the
    # redirect target only as a last-resort fallback.
    redirect_fallback: tuple[str, str, str | None] | None = None  # (fixed, proxy, og)
    for proxy in candidates:
        try:
            passed, og_url, final_url = await _ig_probe(proxy, path)
            if not passed:
                continue
            # Detect whether the proxy actually served the embed itself or
            # 302'd back to instagram.com (common for /reel/ paths).
            served_by_proxy = True
            if final_url:
                final_host = urllib.parse.urlparse(final_url).netloc.lower()
                final_bare = (
                    final_host[4:] if final_host.startswith("www.") else final_host
                )
                served_by_proxy = (
                    final_bare == proxy or final_bare.endswith("." + proxy)
                )
            if served_by_proxy:
                fixed = _instagram_url_with_proxy(clean_original, proxy)
                _log_evt(
                    "ig_convert",
                    proxy=proxy,
                    og=og_url,
                    url=clean_original,
                    fixed=fixed,
                    served_by_proxy=True,
                )
                return fixed, clean_original
            if redirect_fallback is None:
                fallback_url = final_url or _instagram_url_with_proxy(
                    clean_original, proxy,
                )
                redirect_fallback = (fallback_url, proxy, og_url)
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            logger.warning("IG proxy %s probe failed: %s", proxy, e)

    if redirect_fallback is not None:
        fixed, proxy, og_url = redirect_fallback
        _log_evt(
            "ig_convert",
            proxy=proxy,
            og=og_url,
            url=clean_original,
            fixed=fixed,
            served_by_proxy=False,
        )
        return fixed, clean_original

    _log_evt(
        "ig_all_fail",
        tried=candidates,
        override=_ig_proxy_override,
        url=clean_original,
        last_error=last_error,
    )
    return None, clean_original

def _convert_facebook(url: str):
    """Return (fixed_url, clean_url) for Facebook links (any FB-family domain).

    When the input is already on facebookez.com, returns ``(cleaned, None)`` so
    no duplicate "fallback" link is emitted.
    """
    cleaned_url = _clean_query(url)
    parsed = urllib.parse.urlparse(cleaned_url)
    domain = parsed.netloc.lower()
    if domain == "facebookez.com" or domain.endswith(".facebookez.com"):
        return cleaned_url, None
    fixed = urllib.parse.urlunparse((
        parsed.scheme or "https",
        "facebookez.com",
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    return fixed, cleaned_url


async def _convert_tiktok_async(url: str) -> tuple[str | None, str]:
    """Return (fixed_url, clean_url) for TikTok links (app v1.7.0 parity).

    tiktok.com hosts are rewritten to the healthiest proxy from
    TIKTOK_PROXY_ORDER with the subdomain prefix preserved (vm.tiktok.com →
    vm.tnktok.com). Same health policy as Instagram: each candidate is probed
    (with the user's actual path) before the message is sent, a proxy that
    merely redirects back to tiktok.com is only a last-resort fallback, and
    if *every* proxy fails the caller gets (None, clean_url) — log + skip,
    original message stays.

    URLs already on a current proxy are cleaned only (clean_url=None); URLs
    on a legacy proxy (vxtiktok/tiktxk) are migrated to a healthy proxy,
    with the fallback link normalised back to tiktok.com.
    """
    cleaned_url = _clean_query(url)
    parsed = urllib.parse.urlparse(cleaned_url)
    domain = parsed.netloc.lower()
    path = parsed.path or "/"

    known_proxies = tuple(TIKTOK_PROXY_ORDER) + _TIKTOK_PROXY_DOMAINS
    if any(domain == p or domain.endswith("." + p) for p in known_proxies):
        return cleaned_url, None

    source = next(
        (h for h in ("tiktok.com",) + _TIKTOK_LEGACY_PROXIES
         if domain == h or domain.endswith("." + h)),
        None,
    )
    if source is None:
        return cleaned_url, cleaned_url  # defensive fallback

    prefix = domain[: -len(source)]  # "" or "vm." / "vt." / "www." / …

    def _swap_host(new_host: str) -> str:
        return urllib.parse.urlunparse((
            parsed.scheme or "https",
            new_host,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))

    if source != "tiktok.com":
        # Legacy-proxy input: the fallback link must point at tiktok.com,
        # not at the dead legacy host.
        cleaned_url = _swap_host(prefix + "tiktok.com")

    candidates = [p for p in TIKTOK_PROXY_ORDER if not _TT_HEALTH.circuit_should_skip(p)]
    if not candidates:
        # Every breaker open — try them all in half-open state.
        candidates = list(TIKTOK_PROXY_ORDER)

    if not TIKTOK_VERIFY_EMBED:
        return _swap_host(prefix + candidates[0]), cleaned_url

    last_error: str | None = None
    redirect_fallback: tuple[str, str, str | None] | None = None
    for proxy in candidates:
        host = prefix + proxy
        try:
            passed, og_url, final_url = await _tt_probe(proxy, path, host=host)
            if not passed:
                continue
            served_by_proxy = True
            if final_url:
                final_host = urllib.parse.urlparse(final_url).netloc.lower()
                final_bare = (
                    final_host[4:] if final_host.startswith("www.") else final_host
                )
                served_by_proxy = (
                    final_bare == proxy or final_bare.endswith("." + proxy)
                )
            if served_by_proxy:
                fixed = _swap_host(host)
                _log_evt(
                    "tiktok_convert",
                    proxy=proxy,
                    og=og_url,
                    url=cleaned_url,
                    fixed=fixed,
                    served_by_proxy=True,
                )
                return fixed, cleaned_url
            if redirect_fallback is None:
                redirect_fallback = (final_url or _swap_host(host), proxy, og_url)
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            logger.warning("TikTok proxy %s probe failed: %s", proxy, e)

    if redirect_fallback is not None:
        fixed, proxy, og_url = redirect_fallback
        _log_evt(
            "tiktok_convert",
            proxy=proxy,
            og=og_url,
            url=cleaned_url,
            fixed=fixed,
            served_by_proxy=False,
        )
        return fixed, cleaned_url

    _log_evt(
        "tiktok_all_fail",
        tried=candidates,
        url=cleaned_url,
        last_error=last_error,
    )
    return None, cleaned_url

# ------------------------ MESSAGE BUILDER ----------------------------

# Helper to escape Telegram Markdown V2 special characters
def escape_markdown(text: str) -> str:
    if not text:
        return ''
    # Escape all Telegram MarkdownV2 special characters
    return re.sub(r'([_\*\[\]\(\)~`>#+\-=|{}.!])', r'\\\1', text)


def _escape_md_url(url: str) -> str:
    """Escape the two characters that break a MarkdownV2 inline-link URL.

    Without this, URLs containing ')' (e.g. Wikipedia article titles) make
    Telegram reject the whole message with BadRequest.
    """
    return url.replace("\\", "\\\\").replace(")", "\\)")

def _build_message(platform: str, username: str, fixed_url: str, clean_url: str | None, original_url: str, user_text: str = "") -> str:
    """Generate the final Telegram message according to platform template, escaping Markdown entities."""
    esc_username = escape_markdown(username)
    esc_divider = escape_markdown(DIVIDER)
    header = f'_Originally posted by {esc_username} on date and time of this message:_'

    # Build the message with user text if present
    if user_text:
        # Format user text as a blockquote - each line needs to start with >
        # Escape each line's content but not the > character
        quoted_lines = [f'> {escape_markdown(line)}' for line in user_text.split('\n')]
        quoted_text = '\n'.join(quoted_lines)
        header = f'{header}\n\n{quoted_text}'

    # Build MarkdownV2 hyperlink labels with proper escaping. When clean_url
    # is None we have no separate "fallback" link to render, so the primary
    # row drops the "& converted" suffix to read naturally. The 🔄 (loading)
    # icon signals "embed in progress" for converted links; for cleaned-only
    # URLs (no domain rewrite, no embed expected) we use ✅ to indicate the
    # URL is final and ready.
    if clean_url is None:
        label_fixed = escape_markdown("✅ Cleaned URL")
    else:
        label_fixed = escape_markdown("🔄 Cleaned & converted URL")
    label_clean = escape_markdown("✅ Clean URL (if embed isn't available)")
    label_original = escape_markdown("⛔ Original (dirty) URL")

    # Assemble hyperlink strings (URLs must escape only ')' and '\\' inside)
    fixed_link = f"[{label_fixed}]({_escape_md_url(fixed_url)})"
    clean_link = f"[{label_clean}]({_escape_md_url(clean_url)})" if clean_url else None
    original_link = f"[{label_original}]({_escape_md_url(original_url)})"

    # Combine links with single newline
    links = [fixed_link]
    if clean_link:
        links.append(clean_link)
    links.append(original_link)
    links_block = "\n".join(links)

    # Final composed message
    msg = (
        f"{header}\n\n{esc_divider}\n"
        f"{links_block}\n{esc_divider}"
    )
    return msg

# ------------------------ PLATFORM IDENTIFICATION --------------------

# Strict eTLD-aware match: a netloc matches if it is the host itself OR a
# subdomain (".host"). Avoids the substring false-positive where "x.com"
# matched "maxx.com" or "fakeinstagram.scam.com" matched Instagram.
_X_HOSTS = ("x.com", "twitter.com", "fixupx.com", "fxtwitter.com", "vxtwitter.com")
# Identification list intentionally includes both currently-active and
# historically-known proxies so URLs already on a dead proxy get re-routed
# to a working one in _convert_instagram_async.
_INSTAGRAM_HOSTS = ("instagram.com",) + tuple(IG_PROXY_ORDER) + _HISTORICAL_IG_HOSTS
_FACEBOOK_HOSTS = ("facebook.com", "fb.com", "fb.watch")
# NOTE: suffix matching means "kktiktok.com" does NOT accidentally match
# "tiktok.com" (no "." boundary) — each proxy must be listed explicitly.
_TIKTOK_HOSTS = ("tiktok.com",) + _TIKTOK_PROXY_DOMAINS + _TIKTOK_LEGACY_PROXIES


def _host_matches(domain: str, hosts: tuple[str, ...]) -> bool:
    return any(domain == host or domain.endswith("." + host) for host in hosts)


def _identify_platform(domain: str) -> str | None:
    domain = domain.lower()
    if _host_matches(domain, _X_HOSTS):
        return PLATFORM_X
    if _host_matches(domain, _INSTAGRAM_HOSTS):
        return PLATFORM_INSTAGRAM
    if _host_matches(domain, _FACEBOOK_HOSTS):
        return PLATFORM_FACEBOOK
    if _host_matches(domain, _TIKTOK_HOSTS):
        return PLATFORM_TIKTOK
    return None

# ------------------------ MAIN CONVERSION ENTRY ----------------------

async def convert_supported_url(url: str):
    """Detect platform and return (platform, fixed_url, clean_url).

    Mirrors the Android app's UrlProcessor: every URL is run through the
    cleaner engine; X / Instagram / Facebook / TikTok additionally get a
    domain rewrite. Other platforms (YouTube, Reddit, Amazon, Substack, …)
    fall into the PLATFORM_OTHER branch which only strips tracking.

    Return contract:
        (None, None, None)        — URL was already clean and not on a
                                    convert-platform; caller skips it.
        (PLATFORM_OTHER, c, None) — cleaning removed at least one param;
                                    the bot posts the cleaned URL.
        (PLATFORM_X|IG|FB|TIKTOK, f, c) — domain rewrite happened; ``c`` may
                                    be None when the input was already on the
                                    proxy (avoids duplicate links).
        (PLATFORM_INSTAGRAM|TIKTOK, None, c) — all-fail (every proxy failed
                                    the embed health check); caller logs and
                                    leaves the original message intact.
    """
    parsed = urllib.parse.urlparse(url)
    platform = _identify_platform(parsed.netloc)
    if platform == PLATFORM_X:
        fixed, clean = _convert_x(url)
        if fixed == url and clean is None:
            return None, None, None
        return platform, fixed, clean
    if platform == PLATFORM_INSTAGRAM:
        fixed, clean = await _convert_instagram_async(url)
        if fixed == url and clean is None:
            return None, None, None
        return platform, fixed, clean
    if platform == PLATFORM_FACEBOOK:
        fixed, clean = _convert_facebook(url)
        if fixed == url and clean is None:
            return None, None, None
        return platform, fixed, clean
    if platform == PLATFORM_TIKTOK:
        fixed, clean = await _convert_tiktok_async(url)
        if fixed == url and clean is None:
            return None, None, None
        return platform, fixed, clean

    # Any other host: run the cleaner engine. If it didn't change the URL,
    # the bot has nothing useful to add → skip silently.
    cleaned = _clean_query(url)
    if cleaned == url:
        return None, None, None
    return PLATFORM_OTHER, cleaned, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    if update.message is None:
        return  # e.g. channel post or edited message
    await update.message.reply_text(
        "🤖 <b>Hi! I'm FixupXer bot.</b>\n\n"
        "I automatically <b>clean</b> tracking parameters and <b>convert</b> social-media links so they embed beautifully in Telegram.\n\n"
        "🔄 <b>X/Twitter</b>: x.com / twitter.com → fixupx.com / fxtwitter.com\n"
        "📸 <b>Instagram</b>: instagram.com → healthiest embed proxy (toinstagram.com, adamlikes.men, …)\n"
        "🎵 <b>TikTok</b>: tiktok.com → tnktok.com\n"
        "📘 <b>Facebook</b>: facebook.com → facebookez.com\n\n"
        "⚠️ <b>Heads-up</b>: Facebook often hides extra tracking behind secondary links that only activate after clicking on a primary link, so cleaning in most cases is impossible.\n\n"
        "Add me to your group and I'll take care of every supported link automatically.\n\n"
        "The original poster can delete my message at any time by replying with /delete (I need admin rights to delete).",
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    if update.message is None:
        return
    await update.message.reply_text(
        "📝 <b>FixupXer bot – Help</b>\n\n"
        "Simply add me to any chat. Whenever someone posts a supported link, I'll: \n"
        "1. Delete the original message (needs admin rights).\n"
        "2. Repost a cleaned & converted version with proper embeds.\n\n"
        "<b>Supported platforms</b>:\n"
        "🔄 <b>X/Twitter</b>: x.com / twitter.com → fixupx.com / fxtwitter.com\n"
        "📸 <b>Instagram</b>: instagram.com → healthiest embed proxy (toinstagram.com, adamlikes.men, …)\n"
        "🎵 <b>TikTok</b>: tiktok.com → tnktok.com\n"
        "📘 <b>Facebook</b>: facebook.com → facebookez.com\n\n"
        "⚠️ <b>Note</b>: Facebook may still attach hidden tracking after click – I strip everything I can see.\n\n"
        "<b>Commands</b>:\n"
        "• /start – Show welcome information\n"
        "• /help – Show this message\n"
        "• /stats – Bot usage statistics (admins)\n"
        "• /delete – Original poster/Admin can delete my repost\n\n"
        "Need more info? Check the README or open an issue on GitHub.",
        parse_mode="HTML"
    )

def _stats_query_sync() -> dict:
    conn = _db_connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT chat_id) FROM chats")
        total_chats = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM conversions")
        total_conversions = cur.fetchone()[0]
        cur.execute(
            """SELECT c.chat_title, COUNT(*) AS count
               FROM conversions cv JOIN chats c ON cv.chat_id = c.chat_id
               GROUP BY c.chat_id ORDER BY count DESC LIMIT 5"""
        )
        active_chats = cur.fetchall()
        cur.execute(
            """SELECT u.username, COUNT(*) AS count
               FROM conversions cv JOIN users u ON cv.user_id = u.user_id
               GROUP BY u.user_id ORDER BY count DESC LIMIT 5"""
        )
        active_users = cur.fetchall()
    finally:
        conn.close()
    return {
        "total_chats": total_chats,
        "total_users": total_users,
        "total_conversions": total_conversions,
        "active_chats": active_chats,
        "active_users": active_users,
    }


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot usage statistics to authorized users."""
    if update.message is None or update.message.from_user is None:
        return
    user_id = update.message.from_user.id
    if user_id not in BOT_ADMINS:
        await update.message.reply_text("You are not authorized to view bot statistics.")
        return
    if STATS_DISABLED:
        await update.message.reply_text(
            "Statistics collection is disabled (FIXUPXER_DISABLE_STATS=1)."
        )
        return

    data = await asyncio.to_thread(_stats_query_sync)

    parts = [
        "📊 *Bot Statistics*",
        "",
        f"*Total Groups:* {data['total_chats']}",
        f"*Total Users:* {data['total_users']}",
        f"*Total Conversions:* {data['total_conversions']}",
        "",
    ]
    if data["active_chats"]:
        parts.append("*Most Active Groups:*")
        for title, count in data["active_chats"]:
            label = escape_markdown(title or "Unknown")
            parts.append(f"\\- {label}: {count} conversions")
        parts.append("")
    if data["active_users"]:
        parts.append("*Most Active Users:*")
        for username, count in data["active_users"]:
            label = escape_markdown(username or "Unknown")
            parts.append(f"\\- @{label}: {count} conversions")

    await update.message.reply_text("\n".join(parts), parse_mode="MarkdownV2")

async def _delayed_delete(context: ContextTypes.DEFAULT_TYPE) -> None:
    """job_queue callback: delete a message after the scheduled delay.

    PTB v20+ requires an async callable; the previous lambda returned a
    coroutine that was never awaited (silent no-op).
    """
    chat_id, message_id = context.job.data
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:  # noqa: BLE001 - best-effort cleanup
        logger.warning(
            "Delayed delete failed (chat=%s, msg=%s): %s", chat_id, message_id, e
        )


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete: original poster or chat admin can remove the bot's reply.

    Authorisation prefers the in-memory map (fast path) and falls back to the
    SQLite ``delete_tokens`` table so /delete keeps working across bot
    restarts.
    """
    if update.message is None or not update.message.reply_to_message:
        return  # /delete must reply to a message.
    replied = update.message.reply_to_message
    if replied.from_user is None or replied.from_user.id != context.bot.id:
        return  # Only this bot's own reposts can be /delete'd.

    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    bot_message_id = replied.message_id

    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        is_admin = chat_member.status in ["administrator", "creator"]

        is_original_poster = (
            bot_message_id in user_message_map
            and user_message_map[bot_message_id] == user_id
        )
        if not is_original_poster and not is_admin:
            db_user = await _lookup_delete_token(chat_id, bot_message_id)
            is_original_poster = db_user == user_id

        if is_original_poster or is_admin:
            await context.bot.delete_message(chat_id=chat_id, message_id=bot_message_id)
            try:
                await update.message.delete()
            except TelegramError as e:
                logger.warning("Failed to delete /delete command itself: %s", e)
            user_message_map.pop(bot_message_id, None)
            await _remove_delete_token(chat_id, bot_message_id)
            logger.info("Message %s deleted by user %s", bot_message_id, user_id)
        else:
            await update.message.reply_text(
                "You can only delete messages that were originally posted by you.",
                reply_to_message_id=update.message.message_id,
            )
            context.job_queue.run_once(
                _delayed_delete,
                when=5,
                data=(chat_id, update.message.message_id),
            )
    except BadRequest as e:
        logger.error("BadRequest in /delete: %s", e)
        await update.message.reply_text(
            "Failed to delete the message — I might not have admin rights.",
            reply_to_message_id=update.message.message_id,
        )
    except Forbidden as e:
        logger.warning("Forbidden in /delete: %s", e)
    except TelegramError as e:
        logger.error("TelegramError in /delete: %s", e)
    except Exception:
        logger.exception("Unexpected error in /delete")

async def setproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only Instagram proxy override.

    Usage (DM only):
      /setproxy <domain>   force a specific proxy (must be in IG_PROXY_ORDER)
      /setproxy auto       restore automatic fallback
      /setproxy status     show health table for all proxies
    """
    global _ig_proxy_override
    if update.message is None or update.message.from_user is None:
        return
    user_id = update.message.from_user.id
    if user_id not in BOT_ADMINS:
        return  # Silent no-op for non-admins.
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Use /setproxy in a private chat with the bot."
        )
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: /setproxy <domain> | auto | status"
        )
        return
    sub = args[0].strip().lower()

    if sub == "status":
        def _status_row(hc: _ProxyHealthChecker, proxy: str) -> str:
            c = hc.circuit_get(proxy)
            ok, fail = hc.event_counts_1h(proxy)
            state = c["state"]
            if state == "open":
                remaining = max(
                    0,
                    _IG_CIRCUIT_OPEN_SECONDS - int(time.time() - c["opened_ts"]),
                )
                state = f"open({remaining}s)"
            return f"{proxy:<16}{state:<12}{ok}/{fail}"

        rows = ["Instagram       State       Last 1h ok/fail"]
        rows.extend(_status_row(_IG_HEALTH, p) for p in IG_PROXY_ORDER)
        rows.append(f"Override: {_ig_proxy_override or 'auto'}")
        rows.append("")
        rows.append("TikTok          State       Last 1h ok/fail")
        rows.extend(_status_row(_TT_HEALTH, p) for p in TIKTOK_PROXY_ORDER)
        body = "\n".join(rows)
        await update.message.reply_text(
            f"<pre>{html_escape(body)}</pre>", parse_mode="HTML",
        )
        return

    if sub == "auto":
        _ig_proxy_override = None
        await update.message.reply_text("Override cleared; auto-fallback active.")
        return

    if sub not in [p.lower() for p in IG_PROXY_ORDER]:
        allowed = ", ".join(IG_PROXY_ORDER)
        await update.message.reply_text(
            f"Unknown proxy: {sub}. Allowed: {allowed}"
        )
        return

    _ig_proxy_override = sub
    await update.message.reply_text(f"Override set to {sub}.")


async def _background_probe(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic per-proxy probe used to close circuit breakers proactively."""
    if IG_VERIFY_EMBED:
        for proxy in IG_PROXY_ORDER:
            try:
                await _ig_probe(proxy, _IG_BG_PROBE_PATH)
            except Exception as e:  # noqa: BLE001
                logger.warning("Background probe of %s failed: %s", proxy, e)
    if TIKTOK_VERIFY_EMBED:
        for proxy in TIKTOK_PROXY_ORDER:
            try:
                await _tt_probe(proxy, _TT_BG_PROBE_PATH)
            except Exception as e:  # noqa: BLE001
                logger.warning("Background probe of %s failed: %s", proxy, e)


_MAX_URLS_PER_MESSAGE = 3


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find supported URLs in `update.message.text` and post cleaned versions.

    Up to _MAX_URLS_PER_MESSAGE supported URLs are converted, each as its own
    bot reply (Telegram only renders an embed for one URL per message, so a
    single combined reply would only preview the first link). The original
    message is deleted after at least one successful conversion.
    """
    if update.message is None:
        return  # Edited messages / channel posts are intentionally ignored.
    message = update.message.text
    if not message:
        return

    if update.message.from_user is None or update.message.from_user.is_bot:
        return

    raw_candidates = URL_PATTERN.findall(message)
    # Order-preserving dedupe: the same URL pasted twice gets one reply.
    candidates = list(dict.fromkeys(_trim_url_trail(c) for c in raw_candidates))
    if not candidates:
        return

    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    chat_id = update.effective_chat.id

    sent_count = 0
    user_text_attached = False
    stats_tracked = False
    for candidate in candidates:
        if sent_count >= _MAX_URLS_PER_MESSAGE:
            break

        platform, fixed_url, clean_url = await convert_supported_url(candidate)
        if platform is None:
            continue
        if fixed_url is None:
            # All proxies failed the embed health check: log + skip (do not
            # send replacement, do not delete original — "all-fail policy").
            logger.warning(
                "%s all-fail for %s; leaving original message intact.",
                platform,
                candidate,
            )
            continue

        # Attach the user's surrounding text only to the first reply so it
        # isn't duplicated across multi-URL messages.
        if not user_text_attached:
            url_start = message.find(candidate)
            user_text_attached = True
            if url_start >= 0:
                url_end = url_start + len(candidate)
                text_before = message[:url_start].strip()
                text_after = message[url_end:].strip()
                user_text = (text_before + " " + text_after).strip()
            else:
                user_text = ""
        else:
            user_text = ""

        final_message = _build_message(
            platform, username, fixed_url, clean_url, candidate, user_text,
        )

        try:
            bot_message = await context.bot.send_message(
                chat_id=chat_id,
                text=final_message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=False,
            )
        except BadRequest as e:
            # MarkdownV2 escaping bug, message too long, etc. — surface the
            # real reason in logs instead of the misleading admin message.
            logger.error("Telegram BadRequest while sending reply: %s", e)
            continue
        except Forbidden as e:
            logger.warning("Bot is forbidden in chat %s: %s", chat_id, e)
            return
        except TelegramError as e:
            logger.error("Telegram error sending reply: %s", e)
            continue
        except Exception:
            logger.exception("Unexpected error sending reply")
            continue

        user_message_map[bot_message.message_id] = user.id
        await _save_delete_token(bot_message.message_id, chat_id, user.id)
        if not stats_tracked:
            # Lazy stats tracking: users/chats are recorded only when they
            # actually trigger a conversion (matches the README's stats
            # semantics; messages without conversions cost zero DB writes).
            await track_user(user)
            await track_chat(update.effective_chat)
            stats_tracked = True
        # Privacy: store only the cleaned URL (no tracking tokens) in stats.
        await track_conversion(user.id, chat_id, clean_url or fixed_url, fixed_url)

        logger.info(
            "Converted %s -> %s (platform=%s) for %s",
            candidate, fixed_url, platform, username,
        )
        sent_count += 1

    if sent_count == 0:
        return

    try:
        await update.message.delete()
    except BadRequest as e:
        # Most common cause: bot lacks "Delete messages" admin right.
        logger.warning("Failed to delete original message: %s", e)
        with contextlib.suppress(TelegramError):
            await update.message.reply_text(
                "(Note: grant me admin rights to also delete the original message.)",
                disable_web_page_preview=True,
            )
    except Forbidden as e:
        logger.warning("Forbidden when deleting original: %s", e)
    except TelegramError as e:
        logger.warning("TelegramError when deleting original: %s", e)

async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central PTB error handler.

    Transport-level noise (polling conflicts, transient network errors) gets
    one warning line; anything else keeps the full traceback.
    """
    err = context.error
    if isinstance(err, (Conflict, NetworkError)):
        logger.warning("Telegram transport error: %s", err)
        return
    logger.error("Unhandled error while processing an update", exc_info=err)


async def _post_shutdown(_application) -> None:
    """Close httpx and run a SQLite WAL checkpoint on shutdown."""
    global _probe_http_client
    if _probe_http_client is not None:
        try:
            await _probe_http_client.aclose()
        except Exception as e:  # noqa: BLE001
            logger.warning("Error closing httpx client: %s", e)
        _probe_http_client = None
    if not STATS_DISABLED:
        try:
            await asyncio.to_thread(_wal_checkpoint_sync)
        except Exception as e:  # noqa: BLE001
            logger.warning("WAL checkpoint failed: %s", e)


def _wal_checkpoint_sync() -> None:
    conn = _db_connect()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN environment variable is required. "
            "Set it in your shell or in a .env file (see README)."
        )

    init_db()

    application = (
        Application.builder()
        .token(token)
        .post_shutdown(_post_shutdown)
        .build()
    )

    application.add_error_handler(_on_error)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("setproxy", setproxy_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))

    # Periodic proxy probe (IG + TikTok) closes circuit breakers without
    # waiting for real traffic. Disabled when both verify flags are off.
    if (IG_VERIFY_EMBED or TIKTOK_VERIFY_EMBED) and IG_PROBE_INTERVAL_SECONDS > 0:
        application.job_queue.run_repeating(
            _background_probe,
            interval=IG_PROBE_INTERVAL_SECONDS,
            first=10.0,
            name="proxy_background_probe",
        )

    mode = os.environ.get("FIXUPXER_MODE", "polling").strip().lower()
    if mode == "webhook":
        webhook_url = os.environ.get("FIXUPXER_WEBHOOK_URL", "").strip()
        if not webhook_url:
            raise SystemExit(
                "FIXUPXER_MODE=webhook requires FIXUPXER_WEBHOOK_URL "
                "(e.g. https://example.com/telegram)."
            )
        listen = os.environ.get("FIXUPXER_WEBHOOK_LISTEN", "0.0.0.0")
        port = int(os.environ.get("FIXUPXER_WEBHOOK_PORT", "8443"))
        # url_path defaults to the bot token to keep the public URL unguessable
        # if the operator doesn't provide a dedicated path component.
        url_path = os.environ.get("FIXUPXER_WEBHOOK_PATH", token)
        secret_token = os.environ.get("FIXUPXER_WEBHOOK_SECRET") or None
        logger.info("Starting in webhook mode on %s:%s (public URL=%s)", listen, port, webhook_url)
        application.run_webhook(
            listen=listen,
            port=port,
            url_path=url_path,
            webhook_url=webhook_url,
            secret_token=secret_token,
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
