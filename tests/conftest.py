"""Offline tests always use a temporary database and never load deployment secrets."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["FIXUPXER_IG_VERIFY_EMBED"] = "0"
os.environ["FIXUPXER_TIKTOK_VERIFY_EMBED"] = "0"
os.environ["FIXUPXER_DISABLE_STATS"] = "1"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:TEST_TOKEN_NOT_REAL"
os.environ["FIXUPXER_ADMINS"] = ""
os.environ.pop("FIXUPXER_IG_PROXY_ORDER", None)
os.environ.pop("FIXUPXER_TIKTOK_PROXY_ORDER", None)

with patch("dotenv.load_dotenv", return_value=False):
    import fixupxer_bot as bot


@pytest.fixture(autouse=True)
def isolate_bot(monkeypatch, tmp_path):
    monkeypatch.setenv("FIXUPXER_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(bot, "STATS_DISABLED", True)
    monkeypatch.setattr(bot, "IG_VERIFY_EMBED", False)
    monkeypatch.setattr(bot, "TIKTOK_VERIFY_EMBED", False)
    monkeypatch.setattr(bot, "_ig_proxy_override", None)
    monkeypatch.setattr(bot, "_probe_http_client", None)
    monkeypatch.setattr(bot, "_SEND_INTERVAL_GROUP", 0)
    monkeypatch.setattr(bot, "_SEND_INTERVAL_PRIVATE", 0)
    bot.user_message_map.clear()
    bot._last_repost_at.clear()
    bot._CLEAN_CACHE.clear()
    bot.cleaner_engine.DEFAULT_REGISTRY.configure_proxy_domains(
        instagram=bot.IG_PROXY_ORDER, tiktok=bot.TIKTOK_PROXY_ORDER,
    )
    for health in (bot._IG_HEALTH, bot._TT_HEALTH):
        health._url_health.clear()
        health._circuit.clear()
        health._events.clear()
        health._inflight.clear()

    async def no_async_network(*args, **kwargs):
        raise AssertionError("Tests must use a mocked HTTP transport")

    def no_network(*args, **kwargs):
        raise AssertionError("Tests must use a mocked HTTP transport")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_async_network)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
