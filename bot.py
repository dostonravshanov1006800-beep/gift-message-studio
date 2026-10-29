"""Бот (aiogram 3): /start, /gift, /nft, ссылка t.me/nft/... -> макет в личку."""
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, WebAppInfo,
)

import gifts
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


async def send_png(m: Message, png: bytes):
    await m.answer_photo(BufferedInputFile(png, "gift.png"), caption=CAPTION, reply_markup=VIEW_KB)


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
    await send_png(m, rnd.render("stars", sender=sender, stars=stars, ton=ton, usd=usd))


async def nft_from_text(m: Message, text: str, sender: str):
    p = gifts.parse_link(text)
    if not p or p == "unknown":
        return await m.answer("Не нашёл такой подарок, проверь ссылку.")
    try:
        data = await gifts.fetch_nft(*p)
    except Exception as e:  # noqa
        return await m.answer(f"Не получилось получить данные подарка: {e}")
    await send_png(m, rnd.render("nft", sender=sender, nft=data))


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
    await send_png(c.message, rnd.render("stars"))


@dp.callback_query(F.data == "mock_view")
async def mock_view(c: CallbackQuery):
    await c.answer("Это макет, настоящего подарка нет", show_alert=True)


async def run_bot():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)
