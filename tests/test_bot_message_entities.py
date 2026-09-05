"""Message spans and Telegram entities must survive safe repost handling."""
from __future__ import annotations

import pytest
from telegram import MessageEntity, User

import fixupxer_bot as bot
from tests.test_bot_processing import _incoming, _run


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@pytest.mark.parametrize("entity_type", ["spoiler", "code", "pre", "text_link"])
def test_url_inside_protected_entity_is_never_exposed(entity_type):
    prefix = "🔒 "
    url = "https://x.com/secret/status/1?s=20"
    update, context = _incoming(prefix + url)
    options = {"url": "https://actual.example/different-target"} if entity_type == "text_link" else {}
    update.message.entities = (MessageEntity(
        entity_type, _utf16_length(prefix), _utf16_length(url), **options,
    ),)

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_not_awaited()
    update.message.delete.assert_not_awaited()


def test_partial_spoiler_over_url_is_also_protected():
    url = "https://x.com/secret/status/1"
    update, context = _incoming("😀 " + url)
    update.message.entities = (MessageEntity("spoiler", _utf16_length("😀 https://x.com/"), 6),)
    _run(bot.process_message(update, context))
    context.bot.send_message.assert_not_awaited()
    update.message.delete.assert_not_awaited()


def test_visible_repeat_after_spoiler_can_be_processed_without_quoting_spoiler():
    url = "https://x.com/alice/status/1"
    update, context = _incoming(url + " then visible " + url)
    update.message.entities = (MessageEntity("spoiler", 0, _utf16_length(url)),)
    _run(bot.process_message(update, context))
    context.bot.send_message.assert_awaited_once()
    assert "then visible" not in context.bot.send_message.await_args.kwargs["text"]
    update.message.delete.assert_not_awaited()


def test_shorter_candidate_does_not_remove_prefix_of_an_earlier_skipped_url():
    earlier = "https://x.com/a?bad=%ZZ"
    selected = "https://x.com/a"
    text = f"Keep this complete URL: {earlier}\nThen convert: {selected}"
    update, context = _incoming(text)
    update.message.entities = ()

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    sent = context.bot.send_message.await_args.kwargs["text"]
    assert bot.escape_markdown(f"Keep this complete URL: {earlier}") in sent
    assert bot.escape_markdown("Then convert: ") in sent
    assert "https://fixupx.com/a" in sent
    update.message.delete.assert_awaited_once()


def test_hidden_link_target_remains_in_original_instead_of_becoming_plain_label():
    text = "📌 Klik https://x.com/alice/status/1?s=20"
    update, context = _incoming(text)
    hidden = MessageEntity(
        "text_link", _utf16_length("📌 "), len("Klik"),
        url="https://hidden.example/private-resource",
    )
    update.message.entities = (hidden,)

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    sent = context.bot.send_message.await_args.kwargs["text"]
    assert "Klik" not in sent
    assert "https://fixupx.com/alice/status/1" in sent
    update.message.delete.assert_not_awaited()
    assert update.message.entities[0].url == "https://hidden.example/private-resource"


@pytest.mark.parametrize("entity_type", [
    "spoiler", "bold", "italic", "code", "pre", "blockquote",
    "text_mention", "custom_emoji",
])
def test_rich_text_is_not_reposted_as_unformatted_or_exposed_content(entity_type):
    secret = "SensitiveSpoilerValue"
    text = f"{secret} https://x.com/alice/status/1?s=20"
    update, context = _incoming(text)
    options = {}
    if entity_type == "text_mention":
        options["user"] = User(id=123, first_name=secret, is_bot=False)
    if entity_type == "custom_emoji":
        options["custom_emoji_id"] = "123456789"
    update.message.entities = (MessageEntity(entity_type, 0, len(secret), **options),)

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_awaited_once()
    sent = context.bot.send_message.await_args.kwargs["text"]
    assert secret not in sent
    assert "https://fixupx.com/alice/status/1" in sent
    update.message.delete.assert_not_awaited()


def test_plain_url_entity_after_emoji_still_preserves_text_and_allows_safe_deletion():
    prefix = "📌 Keep these  spaces\n"
    url = "https://x.com/alice/status/1?s=20"
    suffix = "\nFinal explanation."
    update, context = _incoming(prefix + url + suffix)
    update.message.entities = (
        MessageEntity("url", _utf16_length(prefix), _utf16_length(url)),
    )

    _run(bot.process_message(update, context))

    sent = context.bot.send_message.await_args.kwargs["text"]
    assert bot.escape_markdown("📌 Keep these  spaces") in sent
    assert bot.escape_markdown("Final explanation.") in sent
    assert "https://fixupx.com/alice/status/1" in sent
    update.message.delete.assert_awaited_once()


def test_mixed_plain_url_and_spoiler_entities_keep_original():
    url = "https://x.com/alice/status/1?s=20"
    secret = "HiddenEnding"
    update, context = _incoming(url + " " + secret)
    update.message.entities = (
        MessageEntity("url", 0, _utf16_length(url)),
        MessageEntity("spoiler", _utf16_length(url + " "), len(secret)),
    )

    _run(bot.process_message(update, context))

    assert secret not in context.bot.send_message.await_args.kwargs["text"]
    update.message.delete.assert_not_awaited()


def test_hidden_link_without_visible_url_is_not_replaced():
    update, context = _incoming("Open this link")
    update.message.entities = (
        MessageEntity("text_link", 0, len(update.message.text),
                      url="https://x.com/alice/status/1?s=20"),
    )

    _run(bot.process_message(update, context))

    context.bot.send_message.assert_not_awaited()
    update.message.delete.assert_not_awaited()


def test_rich_message_above_url_cap_keeps_all_content_in_original():
    secret = "SensitiveSpoilerValue"
    links = " ".join(f"https://x.com/alice/status/{index}?s=20" for index in range(4))
    update, context = _incoming(secret + " " + links)
    update.message.entities = (MessageEntity("spoiler", 0, len(secret)),)

    _run(bot.process_message(update, context))

    assert context.bot.send_message.await_count == 3
    assert all(secret not in call.kwargs["text"]
               for call in context.bot.send_message.await_args_list)
    update.message.delete.assert_not_awaited()
