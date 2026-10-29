"""Бот (aiogram 3): /start, /gift, /nft, ссылка t.me/nft/... -> макет в личку."""
import asyncio
import hashlib
import json
import os
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, WebAppInfo,
)

import gifts
import anim
import render as rnd

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

VIEW_KB = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Посмотреть", callback_data="mock_view")]])
CAPTION = "🎁 Макет сообщения о подарке (не настоящий подарок)"


@dp.message(CommandStart())
async def start(m: Message):
    rows = []
    if WEBAPP_URL.startswith("https://"):
        rows.append([InlineKeyboardButton(text="🎛 Открыть пульт", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.append([InlineKeyboardButton(text="⭐ Пример: 75 звёзд", callback_data="preset_stars")])
    await m.answer(
        "Привет! Я делаю макеты сообщений о подарках Telegram для видео.\n\n"
        "• Открой пульт и настрой всё сам\n"
        "• /gift 75 Имя — звёздный подарок\n"
        "• /nft t.me/nft/LoveCandle-123 Имя — NFT-подарок\n"
        "• или просто пришли ссылку t.me/nft/…\n\n"
        "Это только картинка-макет, настоящих подарков нет.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


CONFETTI_EFFECT = "5046509860389126442"  # 🎉 эффект сообщения; если Telegram не примет, шлём без него
_vcache: dict = {}
_sem = asyncio.Semaphore(2)  # очередь рендера: не больше 2 одновременно


async def build_video(kind, **kw) -> bytes:
    key = hashlib.sha1(json.dumps([kind, kw], sort_keys=True, default=str).encode()).hexdigest()
    hit = _vcache.get(key)
    if hit and time.time() - hit[0] < 24 * 3600:
        return hit[1]
    async with _sem:
        data = await asyncio.to_thread(lambda: anim.make_video(kind, **kw))
    _vcache[key] = (time.time(), data)
    return data


async def send_video(m: Message, kind: str, **kw):
    wait = await m.answer("Готовлю макет…")
    try:
        data = await build_video(kind, **kw)
        f = BufferedInputFile(data, "gift.mp4")
        try:
            await m.answer_video(f, caption=CAPTION, reply_markup=VIEW_KB, width=720, height=1280,
                                 supports_streaming=True, message_effect_id=CONFETTI_EFFECT)
        except Exception:
            await m.answer_video(BufferedInputFile(data, "gift.mp4"), caption=CAPTION, reply_markup=VIEW_KB,
                                 width=720, height=1280, supports_streaming=True)
    finally:
        try:
            await wait.delete()
        except Exception:
            pass


@dp.message(Command("gift"))
async def gift(m: Message, command: CommandObject):
    args = (command.args or "").split(maxsplit=1)
    try:
        stars = int(args[0]) if args else 75
    except ValueError:
        stars = 75
    sender = args[1] if len(args) > 1 else "Неизвестный пользователь"
    ton = f"{stars * 0.0111:.2f}".replace(".", ",")
    usd = f"{stars * 0.015:.2f}".replace(".", ",")
    await send_video(m, "stars", sender=sender, stars=stars, ton=ton, usd=usd)


async def nft_from_text(m: Message, text: str, sender: str):
    p = gifts.parse_link(text)
    if not p or p == "unknown":
        return await m.answer("Не нашёл такой подарок, проверь ссылку.")
    try:
        data = await gifts.fetch_nft(*p)
    except Exception as e:  # noqa
        return await m.answer(f"Не получилось получить данные подарка: {e}")
    await send_video(m, "nft", sender=sender, nft=data)


@dp.message(Command("nft"))
async def nft(m: Message, command: CommandObject):
    args = (command.args or "").split(maxsplit=1)
    if not args:
        return await m.answer("Пример: /nft t.me/nft/LoveCandle-123 Имя")
    await nft_from_text(m, args[0], args[1] if len(args) > 1 else "CaseMint")


@dp.message(F.text.regexp(gifts.NFT_RE))
async def link(m: Message):
    await nft_from_text(m, m.text, "CaseMint")


@dp.callback_query(F.data == "preset_stars")
async def preset(c: CallbackQuery):
    await c.answer()
    await send_video(c.message, "stars")


@dp.callback_query(F.data == "mock_view")
async def mock_view(c: CallbackQuery):
    await c.answer("Это макет, настоящего подарка нет", show_alert=True)


async def run_bot():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)
