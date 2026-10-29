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
    Message, WebAppInfo, BotCommand, MenuButtonWebApp, MenuButtonCommands, ReplyKeyboardMarkup, KeyboardButton,
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
    await m.answer("👇 Кнопка Mini App внизу", reply_markup=app_reply_kb()) if app_reply_kb() else None
    await m.answer(
        "Привет! Я делаю макеты сообщений о подарках Telegram для видео.\n\n"
        "• Открой пульт и настрой всё сам\n"
        "• /gift 75 Имя — звёздный подарок\n"
        "• /nft t.me/nft/LoveCandle-123 Имя — NFT-подарок\n"
        "• или просто пришли ссылку t.me/nft/…\n"
        "• свой подарок: пришли картинку с подписью «Название | номер | модель | фон | узор | отправитель»\n\n"
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


async def send_nft_card(m: Message, nft: dict, sender: str, color=None, button_text="Посмотреть", banner=None):
    """Сценарий «получение подарка» как в Telegram:
    1) строка «X передал(а) Вам подарок!» с эффектом конфетти,
    2) ролик: карточка выпрыгивает, фейерверки и конфетти,
    3) карточка подарка с кнопкой «Посмотреть» (остаётся в чате)."""
    import render as _r
    loop = asyncio.get_event_loop()
    line = banner or f"{sender} передал(а) Вам подарок!"
    try:
        await m.answer(f"<i>{html_escape(line)}</i>", parse_mode="HTML", message_effect_id=CONFETTI_EFFECT)
    except Exception:
        await m.answer(f"<i>{html_escape(line)}</i>", parse_mode="HTML")
    try:
        async with _sem:
            video = await asyncio.to_thread(lambda: anim.make_gift_video(nft, sender, color, button_text))
        await m.answer_video(BufferedInputFile(video, "gift.mp4"), width=720, height=1280, supports_streaming=True)
    except Exception:
        pass  # ролик не критичен: карточка всё равно придёт
    png = await loop.run_in_executor(None, lambda: _r.card_only(nft, sender=sender, color=color, button_text=button_text))
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, callback_data="mock_view")]])
    await m.answer_photo(BufferedInputFile(png, "gift.png"), reply_markup=kb)


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
    await send_nft_card(m, data, sender)


@dp.message(Command("nft"))
async def nft(m: Message, command: CommandObject):
    args = (command.args or "").split(maxsplit=1)
    if not args:
        return await m.answer("Пример: /nft t.me/nft/LoveCandle-123 Имя")
    await nft_from_text(m, args[0], args[1] if len(args) > 1 else "CaseMint")


@dp.message(F.text.regexp(gifts.NFT_RE))
async def link(m: Message):
    await nft_from_text(m, m.text, "CaseMint")


@dp.message(F.web_app_data)
async def from_miniapp(m: Message):
    try:
        p = json.loads(m.web_app_data.data)
    except Exception:
        return await m.answer("Не смог прочитать данные Mini App.")
    kind = p.get("kind", "stars")
    common = dict(banner=(p.get("banner") or None), date_label=(p.get("date") or None),
                  mock_mark=bool(p.get("mock", True)), bg=p.get("bg", "dark"),
                  button_text=(p.get("button") or "Посмотреть")[:24])
    sender = (p.get("sender") or "Неизвестный пользователь")[:40]
    if kind == "stars":
        return await send_video(m, "stars", sender=sender, stars=int(p.get("stars") or 75),
                                ton=str(p.get("ton") or "0,83"), usd=str(p.get("usd") or "1,12"), **common)
    if kind == "nft":
        try:
            slug, num = gifts.parse_link(p.get("link", ""))
            data = await gifts.fetch_nft(slug, num)
        except Exception as e:
            return await m.answer(f"⚠️ {e}")
        return await send_nft_card(m, data, sender, color=data.get("color"), button_text=common["button_text"], banner=common["banner"])
    await m.answer("Для своего подарка пришли картинку с подписью (см. /help).")


# --- «Свой подарок» прямо в чате: фото + подпись "Название | номер | модель | фон | узор" ---
@dp.message(F.photo | F.document)
async def own_gift(m: Message):
    cap = (m.caption or "").strip()
    if not cap:
        return await m.answer(
            "Пришли картинку с подписью:\n<b>Название | номер | модель | фон | узор | имя отправителя</b>\n"
            "Пример: Золотая корона | 777 | Legacy | Mustard | Rose | CaseMint\nНужно только название, остальное по желанию.",
            parse_mode="HTML")
    parts = [x.strip() for x in cap.split("|")] + [""] * 6
    title, num, model, back, sym, sender = parts[:6]
    file_id = m.photo[-1].file_id if m.photo else (m.document.file_id if (m.document and (m.document.mime_type or "").startswith("image/")) else None)
    if not file_id:
        return await m.answer("Нужна картинка (фото или PNG-файл).")
    buf = await bot.download(file_id)
    import base64
    b64 = base64.b64encode(buf.read()).decode()
    nft = {"title": title[:40] or "Мой подарок", "number": num if num.isdigit() else "", "model": model[:30] or "—",
           "backdrop": back[:30] or "—", "symbol": sym[:30] or "—", "color": "#c2593a", "color_edge": "#9a3f26",
           "pattern_color": "#000000", "pattern_text": "", "image_b64": b64}
    await send_nft_card(m, nft, sender[:40] or "Неизвестный пользователь", color=nft["color"])


@dp.callback_query(F.data == "preset_stars")
async def preset(c: CallbackQuery):
    await c.answer()
    await send_video(c.message, "stars")


@dp.callback_query(F.data == "mock_view")
async def mock_view(c: CallbackQuery):
    try:
        await c.answer("Это макет, настоящего подарка нет", show_alert=True)
    except Exception:
        pass  # старая кнопка: Telegram уже закрыл запрос


def app_reply_kb():
    if not WEBAPP_URL.startswith("https://"):
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎛 Открыть Mini App", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True, is_persistent=True)


def app_kb():
    if WEBAPP_URL.startswith("https://"):
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎛 Открыть Mini App", web_app=WebAppInfo(url=WEBAPP_URL))]])
    return None


@dp.message(Command("app"))
async def cmd_app(m: Message):
    kb = app_reply_kb()
    if kb:
        await m.answer("Открой пульт управления кнопкой внизу 👇", reply_markup=kb)
    else:
        await m.answer("Mini App пока не подключён (не задан WEBAPP_URL с https).")


@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "<b>Команды</b>\n"
        "/start — начало\n"
        "/app — открыть Mini App\n"
        "/gift 75 Имя — звёздный подарок\n"
        "/nft t.me/nft/LoveCandle-123 Имя — NFT-подарок\n"
        "/help — эта справка\n\n"
        "Свой подарок: пришли картинку с подписью\n"
        "<code>Название | номер | модель | фон | узор | отправитель</code>",
        parse_mode="HTML", reply_markup=app_kb())


async def setup_menu():
    """Команды в меню «/» и синяя кнопка Mini App слева от поля ввода — для всех пользователей."""
    cmds = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="app", description="Открыть Mini App"),
        BotCommand(command="gift", description="Звёздный подарок: /gift 75 Имя"),
        BotCommand(command="nft", description="NFT-подарок: /nft ссылка Имя"),
        BotCommand(command="help", description="Справка"),
    ]
    await bot.set_my_commands(cmds)
    await bot.set_my_commands(cmds, language_code="ru")
    if WEBAPP_URL.startswith("https://"):
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Mini App", web_app=WebAppInfo(url=WEBAPP_URL)))
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def run_bot():
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await setup_menu()
    except Exception:
        import logging
        logging.getLogger("gms").exception("Не удалось настроить меню (повторится при перезапуске)")
    await dp.start_polling(bot)
