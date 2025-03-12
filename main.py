#!/usr/bin/env python

import html
import json
import tempfile
import traceback
import typing as t

import asyncio
from telegram import Update
from telegram.constants import ParseMode
import telegram
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src import utils, config, memory, agent, audio2text


logger = utils.init_logger()


async def short_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    assert update.message is not None
    if update.message.chat_id != config.app.admin_chat_id:
        await update.message.reply_text("无权限")
        return

    lines = []
    lines.append(f"当前短期记忆数量: {len(memory._short_memory)}")
    if memory._short_memory:
        lines.append("最新的短期记忆:")
        text = json.dumps(memory._short_memory[-1], ensure_ascii=False, indent=2)
        lines.append(text)
    await update.message.reply_text("\n".join(lines))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    assert update.message is not None
    lines = []
    lines.append(f"当前chat id: {update.message.chat_id}")
    lines.append(f"查看短期记忆: /short_memory")
    lines.append(f"该bot可以管理食物、记录饮食和热量、查询食物的营养成分等")
    await update.message.reply_text("\n".join(lines))


async def process_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    assert message is not None
    logger.info(f"audio: {message.to_json()}")
    if message.voice:
        file = await message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg") as f:
            await file.download_to_drive(f.name)
            text = audio2text.qwen_asr(f.name)
    else:
        raise NotImplementedError("audio type not supported")
    await message.reply_text("识别结果: " + text)

    await run_agent(message.chat, update.get_bot(), text, b"")


async def process_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    message = update.message
    assert message is not None
    if message.chat_id != config.app.admin_chat_id:
        await message.reply_text("无权限")
        return
    logger.info(f"message: {message.to_json()}")

    # 解析消息
    text = message.text if message.text else ""
    img_bytes = b""
    if message.photo:
        photo = message.photo[-1]
        file = await update.get_bot().get_file(photo.file_id)
        logger.info(f"photo: {file.to_json()}")
        img_bytes = await file.download_as_bytearray()
        if message.caption:
            text += "\n" + message.caption

    await run_agent(message.chat, update.get_bot(), text, img_bytes)


async def run_agent(
    chat: telegram.Chat, bot: telegram.Bot, text: str, img_bytes: bytes
) -> None:
    # 工具函数
    async def send_text(text: str, **kwargs) -> telegram.Message:
        for k, v in {
            "chat_id": chat.id,
            "text": text,
            "parse_mode": ParseMode.MARKDOWN,
        }.items():
            if k not in kwargs:
                kwargs[k] = v
        try:
            return await bot.send_message(**kwargs)
        except Exception as e:
            logger.error(f"send_text error: {e}")
            kwargs["parse_mode"] = None
            return await bot.send_message(**kwargs)

    # 定义钩子
    fcs = []
    fcm: t.Optional[telegram.Message] = None
    last_edit_time = 0

    async def pre_func_call(_id, name, args):
        nonlocal fcm, fcs, last_edit_time
        fcs.append(f"调用函数: `{name}`")
        current_time = asyncio.get_event_loop().time()
        if not fcm:
            fcm = await send_text("\n".join(fcs), parse_mode=ParseMode.MARKDOWN_V2)
            last_edit_time = current_time
        elif current_time - last_edit_time >= 0.5:
            logger.info(f"edit text: {fcm.text}")
            await fcm.edit_text(text="\n".join(fcs), parse_mode=ParseMode.MARKDOWN_V2)
            last_edit_time = current_time

    async def post_llm_resp(resp: str, short_memory: bool):
        if short_memory:
            resp += "\n*已记录到短期记忆*"
        await send_text(resp)

    hooks = agent.Hooks(pre_func_call=pre_func_call, post_llm_resp=post_llm_resp)

    # 运行agent
    await agent.run_agent(user_text=text, jpg_data=img_bytes, hooks=hooks)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__  # type: ignore
    )
    tb_string = "".join(tb_list)
    light_tb = "".join(tb_list[-5:])  # only the limit lines

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    # await context.bot.send_message(
    #     chat_id=ENV['MY_CHAT_ID'], text=message, parse_mode=ParseMode.HTML
    # )

    message = (
        f"update = {json.dumps(update_str, indent=2, ensure_ascii=False)}"
        f"\ncontext.chat_data = {str(context.chat_data)}"
        f"\ncontext.user_data = {str(context.user_data)}"
    )
    logger.error(message)
    logger.error(tb_string)
    if isinstance(update, Update) and context._chat_id:
        await update.get_bot().send_message(context._chat_id, light_tb)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    token = config.app.bot_token
    application = Application.builder().token(token).build()

    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("short_memory", short_memory))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_text)
    )
    application.add_handler(MessageHandler(filters.PHOTO, process_text))
    application.add_handler(
        MessageHandler(filters.AUDIO | filters.VOICE, process_audio)
    )

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
