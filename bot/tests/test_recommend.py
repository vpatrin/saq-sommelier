from bot.app import recommend_deprecated


async def test_recommend_replies_with_coupette_link_to_chat(update, context):
    await recommend_deprecated(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Coupette" in text
    assert "https://coupette.club/chat" in text


async def test_recommend_ignores_arguments_and_sends_same_deprecation_message(update, context):
    context.args = ["pinot", "noir", "under", "20"]
    await recommend_deprecated(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Coupette" in text
    assert "https://coupette.club/chat" in text


async def test_recommend_omits_saq_affiliation_phrasing(update, context):
    await recommend_deprecated(update, context)

    text = update.message.reply_text.call_args[0][0]
    lowered = text.lower()
    assert "saq" not in lowered
    assert "sommelier" not in lowered
