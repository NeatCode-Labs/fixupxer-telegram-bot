"""Offline tests for explicit link previews and same-message proxy retries."""
from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.error import BadRequest, NetworkError, RetryAfter

import fixupxer_bot as bot
from tests.test_bot_processing import _incoming, _run, _x_url


def _token_from_sent(sent_kwargs):
    markup = sent_kwargs["reply_markup"]
    return markup.inline_keyboard[0][0].callback_data.removeprefix(bot._RETRY_CALLBACK_PREFIX)


def _callback(update, token, *, chat_id=None, user_id=10, message_id=101):
    chat = update.effective_chat
    if chat_id is not None:
        chat = SimpleNamespace(id=chat_id, type=chat.type, title=chat.title)
    query = SimpleNamespace(
        data=f"{bot._RETRY_CALLBACK_PREFIX}{token}",
        message=SimpleNamespace(chat=chat, message_id=message_id),
        from_user=SimpleNamespace(id=user_id),
        answer=AsyncMock(),
    )
    return SimpleNamespace(callback_query=query), query


def _prepare_x_retry(text=None):
    update, context = _incoming(text or _x_url(1))
    _run(bot.process_message(update, context))
    sent = context.bot.send_message.await_args.kwargs
    token = _token_from_sent(sent)
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    callback_update, query = _callback(update, token)
    return update, context, sent, token, callback_update, query


def _prepare_ig_retry():
    update, context = _incoming("https://instagram.com/p/Throttle/?igsh=tracking")
    _run(bot.process_message(update, context))
    sent = context.bot.send_message.await_args.kwargs
    token = _token_from_sent(sent)
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    callback_update, query = _callback(update, token)
    return update, context, sent, token, callback_update, query


def test_every_repost_has_explicit_preview_target_even_with_earlier_link_text():
    update, context = _incoming(f"Earlier {_x_url(1)} then {_x_url(2)}")

    _run(bot.process_message(update, context))

    first = context.bot.send_message.await_args_list[0].kwargs
    assert first["link_preview_options"].url == "https://fixupx.com/alice/status/1"
    assert first["link_preview_options"].is_disabled is False
    assert "disable_web_page_preview" not in first
    assert bot.escape_markdown(_x_url(2)) in first["text"]


def test_x_retry_edits_same_message_to_the_other_proxy_without_reconversion(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, sent, token, callback_update, query = _prepare_x_retry()
    monkeypatch.setattr(
        bot, "convert_supported_url",
        AsyncMock(side_effect=AssertionError("retry must not reconvert")),
    )

    _run(bot.retry_callback(callback_update, context))

    edited = context.bot.edit_message_text.await_args.kwargs
    assert edited["chat_id"] == update.effective_chat.id
    assert edited["message_id"] == 101
    assert edited["link_preview_options"].url == "https://fxtwitter.com/alice/status/1"
    assert edited["text"].count("alice/status/1") >= 1
    assert query.answer.await_count == 1
    assert token in bot._retry_states
    assert update.message.delete.await_count == 1


def test_retry_preserves_tiktok_prefix_functional_query_and_fragment(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    original = "https://vm.tiktok.com/ZMabc/?_r=1&keep=yes#clip"
    update, context = _incoming(original)

    _run(bot.process_message(update, context))

    sent = context.bot.send_message.await_args.kwargs
    assert sent["link_preview_options"].url == (
        "https://vm.tnktok.com/ZMabc/?keep=yes#clip"
    )
    token = _token_from_sent(sent)
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    callback_update, _ = _callback(update, token)
    _run(bot.retry_callback(callback_update, context))

    edited = context.bot.edit_message_text.await_args.kwargs
    assert edited["link_preview_options"].url == (
        "https://vm.tfxktok.com/ZMabc/?keep=yes#clip"
    )
    assert "keep=yes" in edited["link_preview_options"].url
    assert "#clip" in edited["link_preview_options"].url


def test_retry_preserves_instagram_functional_query_and_fragment(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    original = "https://instagram.com/p/ABC/?stkn=gone&img_index=2#comments"
    update, context = _incoming(original)
    _run(bot.process_message(update, context))

    sent = context.bot.send_message.await_args.kwargs
    first_proxy = bot.IG_PROXY_ORDER[0]
    second_proxy = bot.IG_PROXY_ORDER[1]
    assert sent["link_preview_options"].url == (
        f"https://{first_proxy}/p/ABC/?img_index=2#comments"
    )
    token = _token_from_sent(sent)
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    callback_update, _ = _callback(update, token)
    _run(bot.retry_callback(callback_update, context))

    edited = context.bot.edit_message_text.await_args.kwargs
    assert edited["link_preview_options"].url == (
        f"https://{second_proxy}/p/ABC/?img_index=2#comments"
    )


def test_attached_and_compact_text_are_reused_exactly_on_retry(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, sent, token, callback_update, _ = _prepare_x_retry(
        "Keep this exact explanation  with spaces\n" + _x_url(1) + "\nfinish"
    )
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))

    _run(bot.retry_callback(callback_update, context))

    edited_text = context.bot.edit_message_text.await_args.kwargs["text"]
    assert "Keep this exact explanation  with spaces" in sent["text"]
    assert "Keep this exact explanation  with spaces" in edited_text
    assert "finish" in edited_text

    long_update, long_context, long_sent, long_token, long_cb, _ = _prepare_x_retry(
        "x" * 4000 + " " + _x_url(2)
    )
    long_context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    _run(bot.retry_callback(long_cb, long_context))
    assert "x" * 4000 not in long_sent["text"]
    assert "x" * 4000 not in long_context.bot.edit_message_text.await_args.kwargs["text"]


def test_rich_protected_text_stays_hidden_after_retry(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context = _incoming("Secret https://x.com/alice/status/1?s=20")
    update.message.entities = (SimpleNamespace(type="spoiler", offset=0, length=6),)
    _run(bot.process_message(update, context))
    sent = context.bot.send_message.await_args.kwargs
    token = _token_from_sent(sent)
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    callback_update, _ = _callback(update, token)

    _run(bot.retry_callback(callback_update, context))

    assert "Secret" not in sent["text"]
    assert "Secret" not in context.bot.edit_message_text.await_args.kwargs["text"]
    assert update.message.delete.await_count == 0


def test_retry_requires_owner_or_admin_and_binds_chat_and_message(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, _, _ = _prepare_x_retry()
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))

    outsider_update, outsider_query = _callback(update, token, user_id=20)
    context.bot.get_chat_member.return_value = SimpleNamespace(status="member")
    _run(bot.retry_callback(outsider_update, context))
    assert context.bot.edit_message_text.await_count == 0
    assert outsider_query.answer.await_count == 1

    cross_chat_update, cross_chat_query = _callback(update, token, chat_id=-200)
    _run(bot.retry_callback(cross_chat_update, context))
    assert context.bot.edit_message_text.await_count == 0
    assert cross_chat_query.answer.await_count == 1

    wrong_message_update, wrong_message_query = _callback(update, token, message_id=999)
    _run(bot.retry_callback(wrong_message_update, context))
    assert context.bot.edit_message_text.await_count == 0
    assert wrong_message_query.answer.await_count == 1

    context.bot.get_chat_member.return_value = SimpleNamespace(status="administrator")
    admin_update, admin_query = _callback(update, token, user_id=20)
    _run(bot.retry_callback(admin_update, context))
    assert context.bot.edit_message_text.await_count == 1
    assert admin_query.answer.await_count == 1


def test_expired_or_forged_callback_cannot_edit(monkeypatch):
    update, context, _, token, _, _ = _prepare_x_retry()
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    bot._retry_states[token].created_at = time.monotonic() - bot._RETRY_STATE_TTL_SECONDS - 1

    expired_update, expired_query = _callback(update, token)
    _run(bot.retry_callback(expired_update, context))
    forged_update, forged_query = _callback(update, "forged-token")
    _run(bot.retry_callback(forged_update, context))

    assert context.bot.edit_message_text.await_count == 0
    assert expired_query.answer.await_count == 1
    assert forged_query.answer.await_count == 1


def test_failed_edit_does_not_advance_state_or_retry_ambiguous_network_error(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, callback_update, _ = _prepare_x_retry()
    edit = AsyncMock(side_effect=NetworkError("ambiguous"))
    context.bot.edit_message_text = edit
    state = bot._retry_states[token]
    current_used = set(state.used_targets)

    _run(bot.retry_callback(callback_update, context))
    assert edit.await_count == 1
    assert state.used_targets == current_used

    edit.side_effect = None
    second_update, _ = _callback(update, token)
    _run(bot.retry_callback(second_update, context))
    assert edit.await_count == 2
    assert edit.await_args_list[0].kwargs["link_preview_options"].url == edit.await_args_list[1].kwargs["link_preview_options"].url


def test_noop_edit_after_ambiguous_failure_confirms_and_advances(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, callback_update, _ = _prepare_x_retry()
    edit = AsyncMock(side_effect=[
        NetworkError("ambiguous"), BadRequest("Message is not modified"),
    ])
    context.bot.edit_message_text = edit
    state = bot._retry_states[token]
    current_used = set(state.used_targets)

    _run(bot.retry_callback(callback_update, context))
    second_update, _ = _callback(update, token)
    _run(bot.retry_callback(second_update, context))

    assert edit.await_count == 2
    assert state.used_targets != current_used
    assert "fxtwitter.com" in state.fixed_url


def test_explicit_retry_after_is_bounded_and_advances_only_after_success(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, callback_update, _ = _prepare_x_retry()
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    context.bot.edit_message_text = AsyncMock(side_effect=[
        RetryAfter(timedelta(seconds=2)), SimpleNamespace(message_id=101),
    ])
    state = bot._retry_states[token]
    current_used = set(state.used_targets)

    _run(bot.retry_callback(callback_update, context))

    assert context.bot.edit_message_text.await_count == 2
    sleep.assert_awaited_once_with(2.1)
    assert state.used_targets != current_used


def test_excessive_retry_after_is_not_retried_or_advanced(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, callback_update, _ = _prepare_x_retry()
    sleep = AsyncMock()
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    context.bot.edit_message_text = AsyncMock(side_effect=RetryAfter(31))
    state = bot._retry_states[token]
    current_used = set(state.used_targets)

    _run(bot.retry_callback(callback_update, context))

    assert context.bot.edit_message_text.await_count == 1
    sleep.assert_not_awaited()
    assert state.used_targets == current_used


def test_default_click_throttle_rejects_an_immediate_repeat(monkeypatch):
    update, context, _, token, callback_update, first_query = _prepare_ig_retry()
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    _run(bot.retry_callback(callback_update, context))
    second_update, second_query = _callback(update, token)

    _run(bot.retry_callback(second_update, context))

    assert context.bot.edit_message_text.await_count == 1
    assert first_query.answer.await_count == 1
    assert second_query.answer.await_count == 1
    assert second_query.answer.await_args.args[0] == "Please wait before trying another proxy."


def test_retry_state_is_ttl_bound_and_lru_capped(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_STATE_MAX", 2)
    for index in range(3):
        state = bot._new_retry_state(
            chat_id=-100,
            bot_message_id=100 + index,
            owner_id=10,
            platform=bot.PLATFORM_X,
            username="@owner",
            fixed_url=f"https://fixupx.com/p/{index}",
            clean_url=None,
            original_url=f"https://x.com/p/{index}",
            user_text="",
            token=f"token-{index}",
        )
        assert state is not None
        bot._store_retry_state(state)

    assert list(bot._retry_states) == ["token-1", "token-2"]
    bot._retry_states["token-1"].created_at = (
        time.monotonic() - bot._RETRY_STATE_TTL_SECONDS - 1
    )
    assert bot._get_retry_state("token-1") is None
    assert len(bot._retry_states) == 1


def test_concurrent_and_repeated_clicks_are_throttled(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, callback_update, first_query = _prepare_x_retry()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_edit(**kwargs):
        started.set()
        await release.wait()
        return SimpleNamespace(message_id=101)

    context.bot.edit_message_text = AsyncMock(side_effect=slow_edit)
    second_update, second_query = _callback(update, token)

    async def run_clicks():
        first = asyncio.create_task(bot.retry_callback(callback_update, context))
        await started.wait()
        second = asyncio.create_task(bot.retry_callback(second_update, context))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)

    _run(run_clicks())
    assert context.bot.edit_message_text.await_count == 1
    assert first_query.answer.await_count == 1
    assert second_query.answer.await_count == 1


def test_exhaustion_removes_keyboard_and_does_not_send_or_track_again(monkeypatch):
    monkeypatch.setattr(bot, "_RETRY_MIN_INTERVAL_SECONDS", 0)
    update, context, _, token, callback_update, _ = _prepare_x_retry()
    context.bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=101))
    _run(bot.retry_callback(callback_update, context))
    assert context.bot.edit_message_text.await_args.kwargs["reply_markup"] is None

    tracker = AsyncMock()
    monkeypatch.setattr(bot, "track_conversion", tracker)
    second_update, second_query = _callback(update, token)
    _run(bot.retry_callback(second_update, context))

    assert context.bot.send_message.await_count == 1
    assert context.bot.edit_message_text.await_count == 1
    tracker.assert_not_awaited()
    assert second_query.answer.await_count == 1


def test_single_roster_and_other_platforms_have_no_retry_button(monkeypatch):
    monkeypatch.setattr(bot, "IG_PROXY_ORDER", ["only.example"])
    token, markup = bot._initial_retry_markup(
        bot.PLATFORM_INSTAGRAM, "https://only.example/p/1"
    )
    assert token is None and markup is None
    token, markup = bot._initial_retry_markup(
        bot.PLATFORM_OTHER, "https://example.com/p/1"
    )
    assert token is None and markup is None


def test_successful_delete_clears_retry_state():
    update, context, _, token, _, _ = _prepare_x_retry()
    update.message.reply_to_message = SimpleNamespace(
        from_user=SimpleNamespace(id=context.bot.id), message_id=101,
    )
    _run(bot.delete_command(update, context))
    assert token not in bot._retry_states
