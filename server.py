"""FastAPI: раздаёт Mini App и принимает запросы «Показать в чате» с проверкой подписи initData."""
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from urllib.parse import parse_qsl

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import gifts
import render as rnd

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
app = FastAPI()
WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")

_hits = defaultdict(lambda: deque())  # user_id -> timestamps


def check_init_data(init_data: str) -> dict:
    """Проверка подписи Telegram WebApp initData (HMAC-SHA256)."""
    if not init_data:
        raise HTTPException(401, "no initData")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    recv_hash = pairs.pop("hash", None)
    if not recv_hash:
        raise HTTPException(401, "no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recv_hash):
        raise HTTPException(401, "bad signature")
    if time.time() - int(pairs.get("auth_date", "0")) > 86400:
        raise HTTPException(401, "expired")
    return json.loads(pairs["user"])


def rate_limit(uid: int, limit=3, per=60):
    q = _hits[uid]
    now = time.time()
    while q and now - q[0] > per:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Слишком часто, подожди минуту")
    q.append(now)


@app.get("/api/nft")
async def api_nft(link: str):
    p = gifts.parse_link(link)
    if not p or p == "unknown":
        raise HTTPException(404, "Не нашёл такой подарок, проверь ссылку")
    try:
        return await gifts.fetch_nft(*p)
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))


@app.get("/api/backdrops")
async def api_backdrops():
    return gifts.BACKDROPS


@app.post("/api/send")
async def api_send(req: Request):
    body = await req.json()
    user = check_init_data(body.get("initData", ""))
    uid = int(user["id"])
    rate_limit(uid)
    p = body.get("params", {})
    kind = p.get("kind", "stars")
    nft = p.get("nft")
    png = rnd.render(
        kind,
        sender=(p.get("sender") or "Неизвестный пользователь")[:40],
        stars=int(p.get("stars") or 75),
        ton=str(p.get("ton") or "0,83"),
        usd=str(p.get("usd") or "1,12"),
        nft=nft,
        color=p.get("color"),
        banner=(p.get("banner") or None),
        date_label=(p.get("date") or None),
        mock_mark=bool(p.get("mock", True)),
        bg=p.get("bg", "dark"),
        bg_custom=p.get("bgColor"),
        button_text=(p.get("button") or "Посмотреть")[:24],
    )
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": uid,
                "caption": "🎁 Макет сообщения о подарке (не настоящий подарок)" if p.get("mock", True) else "",
                "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Посмотреть", "callback_data": "mock_view"}]]}),
            },
            files={"photo": ("gift.png", png, "image/png")},
        )
    if r.status_code != 200:
        raise HTTPException(502, "Telegram не принял картинку")
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
