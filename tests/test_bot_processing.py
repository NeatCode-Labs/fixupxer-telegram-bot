"""Offline regression tests for Telegram delivery, ownership and privacy."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter

import fixupxer_bot as bot


def _run(coro):
    return asyncio.run(coro)


def test_telegram_payload_debug_logs_stay_disabled_when_root_logging_is_debug(caplog):
    secret = "private-user-message-and-link"
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("telegram.ext.Application").debug("Processing update %s", secret)
    assert secret not in caplog.text


def _incoming(text="", *, chat_id=-100, user_id=10, thread_id=None, chat_type="supergroup"):
    user = SimpleNamespace(
        id=user_id, username="original_poster", first_name="Original",
        last_name="Poster", is_bot=False,
    )
    chat = SimpleNamespace(id=chat_id, type=chat_type, title="Test group")
    message = SimpleNamespace(
        text=text, from_user=user, message_id=90, message_thread_id=thread_id,
        entities=(),
        reply_to_message=None, delete=AsyncMock(), reply_text=AsyncMock(),
    )
    client = SimpleNamespace(
        id=9999,
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=101)),
        delete_message=AsyncMock(),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
    )
    update = SimpleNamespace(message=message, effective_chat=chat, effective_user=user)
    context = SimpleNamespace(bot=client, job_queue=SimpleNamespace(run_once=Mock()))
    return update, context


def _delete_update(*, chat_id=-100, user_id=10, target_id=101):
    update, context = _incoming("/delete", chat_id=chat_id, user_id=user_id)
    update.message.reply_to_message = SimpleNamespace(
        from_user=SimpleNamespace(id=context.bot.id), message_id=target_id,
    )
    return update, context


def _x_url(index):
    return f"https://x.com/alice/status/{index}?s=20"


def _enable_stats(monkeypatch):
    monkeypatch.setattr(bot, "STATS_DISABLED", False)
    bot.init_db()


def test_delete_cache_does_not_grant_ownership_from_another_chat():
    bot._remember_poster(-100, 101, 10)
    bot._remember_poster(-200, 101, 20)
    update, context = _delete_update(chat_id=-100, user_id=20)

    _run(bot.delete_command(update, context))

    context.bot.delete_message.assert_not_awaited()
    update.message.delete.assert_not_awaited()
    update.message.reply_text.assert_awaited_once()
    assert bot.user_message_map[(-100, 101)] == 10
    assert bot.user_message_map[(-200, 101)] == 20


def test_delete_original_owner_uses_cache_without_admin_lookup(monkeypatch):
    bot._remember_poster(-100, 101, 10)
    bot._remember_poster(-200, 101, 20)
    lookup = AsyncMock(side_effect=AssertionError("Cache hit should not read the DB"))
    monkeypatch.setattr(bot, "_lookup_delete_token", lookup)
    update, context = _delete_update()

    _run(bot.delete_command(update, context))

    context.bot.delete_message.assert_awaited_once_with(chat_id=-100, message_id=101)
    update.message.delete.assert_awaited_once()
    context.bot.get_chat_member.assert_not_awaited()
    lookup.assert_not_awaited()
    assert (-100, 101) not in bot.user_message_map
    assert bot.user_message_map[(-200, 101)] == 20


def test_delete_owner_falls_back_to_database_after_cache_is_lost(monkeypatch):
    _enable_stats(monkeypatch)
    bot._delete_token_save_sync(101, -100, 10)
    bot._delete_token_save_sync(101, -200, 20)
    update, context = _delete_update()

    _run(bot.delete_command(update, context))

    context.bot.delete_message.assert_awaited_once_with(chat_id=-100, message_id=101)
    context.bot.get_chat_member.assert_not_awaited()
    assert bot._delete_token_lookup_sync(-100, 101) is None
    assert bot._delete_token_lookup_sync(-200, 101) == 20


@pytest.mark.parametrize("status", ["administrator", "creator"])
def test_delete_chat_admin_can_delete_another_authors_repost(status):
    bot._remember_poster(-100, 101, 10)
    update, context = _delete_update(user_id=20)
    context.bot.get_chat_member.return_value = SimpleNamespace(status=status)

    _run(bot.delete_command(update, context))

    context.bot.get_chat_member.assert_awaited_once_with(-100, 20)
    context.bot.delete_message.assert_awaited_once_with(chat_id=-100, message_id=101)


def test_delete_ignores_messages_from_other_bots():
    update, context = _delete_update()
    update.message.reply_to_message.from_user.id = 12345

    _run(bot.delete_command(update, context))

    context.bot.get_chat_member.assert_not_awaited()
    context.bot.delete_message.assert_not_awaited()


def test_first_send_failure_preserves_original_and_retries_surrounding_text_on_next_link():
    text = f"Keep my full explanation\n{_x_url(1)}\n{_x_url(2)}"
    update, context = _incoming(text)
    context.bot.send_message.side_effect = [
        BadRequest("Synthetic send failure"), SimpleNamespace(message_id=102),
    ]

    _run(bot.process_message(update, context))

    assert context.bot.send_message.await_count == 2
    second = context.bot.send_message.await_args_list[1].kwargs["text"]
    assert "Keep my full explanation" in second
    assert bot.escape_markdown(_x_url(1)) in second
    update.message.delete.assert_not_awaited()
    assert bot.user_message_map[(-100, 102)] == 10


def test_later_send_failure_keeps_original_with_text_in_the_successful_first_repost():
    update, context = _incoming(f"Keep explanation {_x_url(1)} {_x_url(2)}")
    context.bot.send_message.side_effect = [
        SimpleNamespace(message_id=101), NetworkError("Ambiguous request failure"),
    ]

    _run(bot.process_message(update, context))

    assert context.bot.send_message.await_count == 2
    assert "Keep explanation" in context.bot.send_message.await_args_list[0].kwargs["text"]
    update.message.delete.assert_not_awaited()


def test_complete_delivery_deletes_original_only_after_every_repost():
    update, context = _incoming(f"My explanation {_x_url(1)} {_x_url(2)}")
    context.bot.send_message.side_effect = [
        SimpleNamespace(message_id=101), SimpleNamespace(message_id=102),
    ]
    operations = Mock()
    operations.attach_mock(context.bot.send_message, "send")
    operations.attach_mock(update.message.delete, "delete")

    _run(bot.process_message(update, context))

    assert [operation[0] for operation in operations.mock_calls] == ["send", "send", "delete"]
    assert "My explanation" in context.bot.send_message.await_args_list[0].kwargs["text"]
    assert "My explanation" not in context.bot.send_message.await_args_list[1].kwargs["text"]
    assert bot.user_message_map[(-100, 101)] == bot.user_message_map[(-100, 102)] == 10


def test_more_than_three_links_caps_reposts_and_retains_original():
    update, context = _incoming(" ".join(_x_url(index) for index in range(5)))

    _run(bot.process_message(update, context))

    assert context.bot.send_message.await_count == 3
    update.message.delete.assert_not_awaited()


def test_repeated_identical_link_is_reposted_once():
    update, context = _incoming(f"{_x_url(1)} {_x_url(1)}")

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    update.message.delete.assert_awaited_once()


def test_instagram_stkn_message_delivers_clean_links_before_deleting_original(monkeypatch):
    monkeypatch.setattr(bot, "IG_CACHE_BUST", False)
    original = "https://www.instagram.com/reel/Synthetic/?stkn=tracking&img_index=2"
    clean = "https://www.instagram.com/reel/Synthetic/?img_index=2"
    fixed = f"https://{bot.IG_PROXY_ORDER[0]}/reel/Synthetic/?img_index=2"
    update, context = _incoming(f"Keep this explanation {original}", thread_id=42)
    operations = Mock()
    operations.attach_mock(context.bot.send_message, "send")
    operations.attach_mock(update.message.delete, "delete")

    _run(bot.process_message(update, context))

    assert [operation[0] for operation in operations.mock_calls] == ["send", "delete"]
    sent = context.bot.send_message.await_args.kwargs
    assert sent["message_thread_id"] == 42
    assert "Keep this explanation" in sent["text"]
    assert f"]({fixed})" in sent["text"]
    assert f"]({clean})" in sent["text"]
    assert f"]({original})" in sent["text"]  # Explicit original link remains available.


@pytest.mark.parametrize("text", ["No link here", "https://example.com/already-clean"])
def test_messages_with_nothing_to_process_are_untouched(text):
    update, context = _incoming(text)

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_not_awaited()
    update.message.delete.assert_not_awaited()


@pytest.mark.parametrize("surrounding", ["a" * 4000, "🙂" * 2000])
def test_long_text_gets_compact_repost_and_keeps_the_complete_original(surrounding):
    update, context = _incoming(f"{surrounding} {_x_url(1)}")

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    outgoing = context.bot.send_message.await_args.kwargs["text"]
    assert surrounding not in outgoing
    assert "https://fixupx.com/alice/status/1" in outgoing
    assert bot._fits_telegram_message(outgoing)
    update.message.delete.assert_not_awaited()


@pytest.mark.parametrize(
    "text, fits",
    [("x" * 4096, True), ("x" * 4097, False), ("🙂" * 2048, True), ("🙂" * 2049, False)],
)
def test_message_length_counts_emoji_utf16_pairs(text, fits):
    assert bot._fits_telegram_message(text) is fits


def test_url_that_cannot_fit_even_compact_reply_is_not_sent():
    update, context = _incoming("https://x.com/" + "a" * 2000)

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_not_awaited()
    update.message.delete.assert_not_awaited()


def test_unavailable_proxies_mixed_with_success_keep_original(monkeypatch):
    original_ig = "https://instagram.com/p/unavailable/"
    update, context = _incoming(f"Important explanation {original_ig} {_x_url(1)}")
    monkeypatch.setattr(bot, "convert_supported_url", AsyncMock(side_effect=[
        (bot.PLATFORM_INSTAGRAM, None, original_ig),
        (bot.PLATFORM_X, "https://fixupx.com/alice/status/1", "https://x.com/alice/status/1"),
    ]))

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    assert "Important explanation" in context.bot.send_message.await_args.kwargs["text"]
    update.message.delete.assert_not_awaited()


def test_conversion_exception_does_not_prevent_later_repost_or_remove_original(monkeypatch):
    update, context = _incoming(f"{_x_url(1)} {_x_url(2)}")
    monkeypatch.setattr(bot, "convert_supported_url", AsyncMock(side_effect=[
        ValueError("Malformed first URL"),
        (bot.PLATFORM_X, "https://fixupx.com/alice/status/2", "https://x.com/alice/status/2"),
    ]))

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    update.message.delete.assert_not_awaited()


@pytest.mark.parametrize("thread_id", [None, 700])
def test_repost_preserves_forum_topic_when_present(thread_id):
    update, context = _incoming(_x_url(1), thread_id=thread_id)

    _run(bot.process_message(update, context))

    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == update.effective_chat.id
    if thread_id is None:
        assert "message_thread_id" not in kwargs
    else:
        assert kwargs["message_thread_id"] == thread_id


@pytest.mark.parametrize("retry_after", [2, timedelta(seconds=2)])
def test_explicit_rate_limit_waits_then_retries_with_same_topic(monkeypatch, retry_after):
    update, context = _incoming(thread_id=55)
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    reply = SimpleNamespace(message_id=123)
    context.bot.send_message.side_effect = [RetryAfter(retry_after), reply]

    actual = _run(bot._send_repost(context.bot, update.effective_chat, "text", 55))

    assert actual is reply
    sleep.assert_awaited_once_with(pytest.approx(2.1))
    assert context.bot.send_message.await_count == 2
    assert context.bot.send_message.await_args_list[0] == context.bot.send_message.await_args_list[1]


def test_rate_limit_retries_stop_at_the_configured_bound(monkeypatch):
    update, context = _incoming()
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    context.bot.send_message.side_effect = RetryAfter(1)

    with pytest.raises(RetryAfter):
        _run(bot._send_repost(context.bot, update.effective_chat, "text", None))

    assert context.bot.send_message.await_count == bot._SEND_RETRY_LIMIT + 1
    assert sleep.await_count == bot._SEND_RETRY_LIMIT


@pytest.mark.parametrize("retry_after", [31, timedelta(seconds=31)])
def test_excessive_retry_after_is_not_waited_or_retried(monkeypatch, retry_after):
    update, context = _incoming()
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    context.bot.send_message.side_effect = RetryAfter(retry_after)

    with pytest.raises(RetryAfter):
        _run(bot._send_repost(context.bot, update.effective_chat, "text", None))

    context.bot.send_message.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.parametrize("failure", [NetworkError("Unknown delivery"), Forbidden("Blocked")])
def test_ambiguous_or_forbidden_delivery_is_not_automatically_retried(monkeypatch, failure):
    update, context = _incoming()
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    context.bot.send_message.side_effect = failure

    with pytest.raises(type(failure)):
        _run(bot._send_repost(context.bot, update.effective_chat, "text", None))

    context.bot.send_message.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.parametrize("chat_type, interval", [("private", 1.05), ("supergroup", 3.1)])
def test_consecutive_reposts_observe_per_chat_interval(monkeypatch, chat_type, interval):
    update, context = _incoming(chat_type=chat_type)
    monkeypatch.setattr(bot, "_SEND_INTERVAL_PRIVATE", 1.05)
    monkeypatch.setattr(bot, "_SEND_INTERVAL_GROUP", 3.1)
    monkeypatch.setattr(bot.time, "monotonic", Mock(return_value=100.0))
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)

    async def deliver():
        await bot._send_repost(context.bot, update.effective_chat, "first", None)
        await bot._send_repost(context.bot, update.effective_chat, "second", None)

    _run(deliver())

    sleep.assert_awaited_once_with(pytest.approx(interval))


@pytest.mark.parametrize("operation", ["_save_delete_token", "track_user", "track_chat", "track_conversion"])
def test_metadata_failure_preserves_original_and_memory_ownership(monkeypatch, operation):
    update, context = _incoming(_x_url(1))
    monkeypatch.setattr(bot, operation, AsyncMock(side_effect=RuntimeError("DB unavailable")))

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    update.message.delete.assert_not_awaited()
    assert bot.user_message_map[(-100, 101)] == 10


def test_new_stats_omit_urls_while_preserving_old_rows_and_aggregate_counts(monkeypatch):
    _enable_stats(monkeypatch)
    update, context = _incoming(_x_url(1))
    bot._track_user_sync(10, "original_poster", "Original", "Poster")
    bot._track_chat_sync(-100, "Test group", "supergroup")
    old_url = "https://example.com/legacy-private?secret=kept-history"
    connection = bot._db_connect()
    try:
        connection.execute(
            "INSERT INTO conversions (user_id, chat_id, original_url, converted_url) VALUES (?, ?, ?, ?)",
            (10, -100, old_url, old_url),
        )
        connection.commit()
    finally:
        connection.close()

    _run(bot.process_message(update, context))

    connection = bot._db_connect()
    try:
        rows = connection.execute(
            "SELECT original_url, converted_url FROM conversions ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
    assert rows == [(old_url, old_url), (None, None)]
    data = bot._stats_query_sync()
    assert data["total_conversions"] == 2
    assert data["total_groups"] == 1
    assert data["total_users"] == 1
    assert data["active_chats"] == [("Test group", 2)]
    assert data["active_users"] == [("original_poster", 2)]
    monkeypatch.setattr(bot, "BOT_ADMINS", [10])
    _run(bot.stats_command(update, context))
    stats = update.message.reply_text.await_args.args[0]
    assert "*Total Conversions:* 2" in stats
    assert old_url not in stats


def test_log_messages_do_not_expose_urls_user_text_or_exception_secrets(monkeypatch, caplog):
    secret = "UNIQUE_PRIVATE_SECRET_123"
    url = f"https://x.com/private/status/123?token={secret}"
    update, context = _incoming(f"{secret} {url}")
    caplog.set_level(logging.INFO, logger=bot.__name__)

    _run(bot.process_message(update, context))
    context.bot.send_message.side_effect = NetworkError(url)
    _run(bot.process_message(update, context))
    monkeypatch.setattr(bot, "convert_supported_url", AsyncMock(side_effect=ValueError(secret)))
    _run(bot.process_message(update, context))
    bot._log_evt("proxy_failed", url=url, path=secret, last_error=secret, proxy="safe.example")
    _run(bot._on_error(update, SimpleNamespace(error=RuntimeError(url))))
    _run(bot._on_error(update, SimpleNamespace(error=NetworkError(secret))))

    assert secret not in caplog.text
    assert url not in caplog.text
    assert "NetworkError" in caplog.text
    assert "safe.example" in caplog.text


def test_failed_delete_preserves_ownership_and_redacts_exception_details(caplog):
    secret = "PRIVATE_DELETE_ERROR_URL"
    bot._remember_poster(-100, 101, 10)
    update, context = _delete_update()
    context.bot.delete_message.side_effect = BadRequest(secret)
    caplog.set_level(logging.INFO, logger=bot.__name__)

    _run(bot.delete_command(update, context))

    assert bot.user_message_map[(-100, 101)] == 10
    update.message.delete.assert_not_awaited()
    assert secret not in caplog.text
