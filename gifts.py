"""Данные: коллекции NFT, пресеты фонов, парсинг ссылки t.me/nft/..., получение данных подарка."""
import asyncio
import json
import os
import re
import time
import httpx

COLLECTIONS = """ChillFlame, LibertyFigure, ViceCream, SnoopDogg, InstantRamen, PoolFloat, LolPop, IceCream, MoodPack, HappyBrownie, SwagBag, LunarSnake, XmasStocking, WhipCupcake, CandyCane, CloverPin, SnakeBox, FreshSocks, FaithAmulet, PetSnake, MousseCake, JesterHat, CookieHeart, PartySparkler, BDayCandle, SnoopCigar, TimelessBook, SpringBasket, PrettyPosy, LightSword, VictoryMedal, InputKey, FinePen, HomemadeCake, GingerCookie, JellyBunny, MoonPendant, StellarRocket, JollyChimp, SpyAgaric, DeskCalendar, LushBouquet, TamaGadget, RestlessJar, HolidayDrink, JoyfulBundle, SurgeBoard, EvilEye, UFCStrike, HypnoLollipop, EasterEgg, SpicedWine, SakuraFlower, MoneyPot, BigYear, StarNotepad, JackInTheBox, WinterWreath, HexPot, BunnyMuffin, WitchHat, BerryBox, BowTie, EternalCandle, SantaHat, JingleBells, SkyStilettos, ValentineBox, HangingStar, LovePotion, KhabibsPapakha, SnowGlobe, TrappedHeart, CupidCharm, CrystalBall, DiamondRing, TopHat, LoveCandle, EternalRose, ToyBear, IonicDryer, FlyingBroom, RecordPlayer, VintageCigar, SnowMittens, SkullFlower, SleighBell, SignetRing, MadPumpkin, RareBird, LowRider, SwissWatch, VoodooDoll, BlingBinky, NekoHelmet, PerfumeBottle, MagicPotion, ElectricSkull, SharpTongue, KissedFrog, BondedRing, GemSignet, WestsideSign, GenieLamp, NailBracelet, DurovsGlasses, ScaredCat, IonGem, LootBag, PreciousPeach, AstralShard, MiniOscar, ArtisanBrick, DurovsCap, HeroicHelmet, MightyArm, PlushPepe, HeartLocket"""
COLLECTION_SET = {c.strip().lower(): c.strip() for c in COLLECTIONS.split(",")}

SPECIAL_NAMES = {
    "ufcstrike": "UFC Strike",
    "bdaycandle": "B-Day Candle",
    "durovscap": "Durov’s Cap",
    "durovsglasses": "Durov’s Glasses",
    "khabibspapakha": "Khabib’s Papakha",
}

NFT_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/nft/([A-Za-z0-9_]+?)-(\d*)(?![A-Za-z0-9_])", re.I)


def pretty_name(slug: str) -> str:
    low = slug.lower()
    if low in SPECIAL_NAMES:
        return SPECIAL_NAMES[low]
    real = COLLECTION_SET.get(low, slug)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", real)


def parse_link(text: str):
    """Любая ссылка t.me/nft/Имя-число. Если номер не указан, берём случайный (для демо). Список коллекций не нужен."""
    m = NFT_RE.search(text or "")
    if not m:
        return None
    slug, num = m.group(1), m.group(2)
    slug = COLLECTION_SET.get(slug.lower(), slug)
    if not num:
        import random
        num = random.randint(1, 3000)
    return slug, int(num)


_cache: dict = {}
_tg_lock = asyncio.Lock()
_last_tg = [0.0]


async def _tg_wait():
    """Не чаще одного обращения к t.me раз в 1,2 с, иначе Telegram отдаёт пустую заглушку."""
    gap = 1.2 - (time.time() - _last_tg[0])
    if gap > 0:
        await asyncio.sleep(gap)
    _last_tg[0] = time.time()

TTL = 24 * 3600          # кэш в памяти
DISK_TTL = 365 * 24 * 3600  # на диске подарок неизменен: храним год
CACHE_DIR = os.path.join("cache", "nft")


def _disk_get(key):
    try:
        p = os.path.join(CACHE_DIR, key + ".json")
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < DISK_TTL:
            return json.load(open(p, encoding="utf-8"))
    except Exception:
        pass
    return None


def _disk_put(key, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(data, open(os.path.join(CACHE_DIR, key + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


async def fetch_nft(slug: str, num: int) -> dict:
    key0 = f"{slug}-{num}".lower()
    if key0 in _cache or _disk_get(key0):
        return await _fetch_nft(slug, num)
    async with _tg_lock:
        return await _fetch_nft(slug, num)


async def _fetch_nft(slug: str, num: int) -> dict:
    key = f"{slug}-{num}".lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    disk = _disk_get(key)
    if disk:
        _cache[key] = (time.time(), disk)
        return disk

    hosts = ["t.me", "telegram.me"]
    uas = ["curl/8.0", "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
           "python-httpx/0.27", "Mozilla/5.0", "TelegramBot (like TwitterBot)", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"]
    html = ""
    missing = 0
    last_err = None
    # Telegram иногда отдаёт укороченную страницу без SVG (цвета/узор): повторяем, меняя адрес и User-Agent
    for attempt in range(10):
        if attempt:
            await asyncio.sleep(min(0.6 * attempt, 3))
        url = f"https://{hosts[attempt % 2]}/nft/{slug}-{num}"
        try:
            await _tg_wait()
            async with httpx.AsyncClient(timeout=8, follow_redirects=False) as c:
                r = await c.get(url, headers={"User-Agent": uas[attempt % len(uas)], "Accept-Language": "en"})
            if r.status_code in (301, 302, 303, 307, 308):
                loc = r.headers.get("location", "")
                if "/nft/" not in loc:  # ушёл на главную: такого подарка нет
                    missing += 1
                    if missing >= 2:
                        raise LookupError(f"Подарка {slug}-{num} не существует. Попробуй другой номер.")
                    continue
                async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
                    r = await c.get(url, headers={"User-Agent": uas[attempt % len(uas)], "Accept-Language": "en"})
            if r.status_code == 200:
                if not html or ("stop-color" in r.text and "stop-color" not in html):
                    html = r.text
                if "stop-color" in html:
                    break
        except LookupError:
            raise
        except Exception as e:  # noqa
            last_err = e
    if not html or "stop-color" not in html:
        raise RuntimeError("Telegram сейчас не отдаёт данные этого подарка (лимит запросов). Подожди минуту и повтори.")

    def row(label: str):
        m = re.search(
            r"<th[^>]*>\s*" + label + r"\s*</th>\s*<td[^>]*>(.*?)</td>", html, re.S | re.I
        )
        if not m:
            return ""
        val = re.sub(r"<[^>]+>", "", m.group(1))
        val = re.sub(r"\s+", " ", val).strip()
        return re.sub(r"\s*\d+(\.\d+)?%\s*$", "", val).strip()

    model, backdrop, symbol = row("Model"), row("Backdrop"), row("Symbol")
    if not model:
        d = re.search(r'name="twitter:description"\s+content="([^"]*)"', html)
        if d:
            txt = d.group(1)
            for lab, var in (("Model", "model"), ("Backdrop", "backdrop"), ("Symbol", "symbol")):
                mm = re.search(lab + r":\s*([^\n\r]+)", txt)
                if mm:
                    val = re.sub(r"\s*\d+(\.\d+)?%\s*$", "", mm.group(1)).strip()
                    if var == "model":
                        model = val
                    elif var == "backdrop":
                        backdrop = val
                    else:
                        symbol = val

    stops = re.findall(r'stop-color="(#[0-9a-fA-F]{6})"', html)
    flood = re.findall(r'flood-color="(#[0-9a-fA-F]{6})"', html)
    pat_m = re.search(r'<image id="giftPattern"[^>]*xlink:href="([^"]+)"', html)
    places = [
        (float(o), float(x), float(y), float(s))
        for o, x, y, s in re.findall(
            r'<g opacity="([\d.]+)" transform="translate\(([-\d.]+), ([-\d.]+)\)">\s*<use xlink:href="#giftPattern" transform="scale\(([\d.]+)\)"',
            html)
    ]
    tt = re.search(r'<meta property="og:title" content="([^"]*?)\s*#\d+"', html)
    page_title = re.sub(r"\s+", " ", tt.group(1)).strip() if tt else ""
    data = {
        "slug": slug,
        "number": num,
        "title": page_title or pretty_name(slug),
        "model": model or "—",
        "backdrop": backdrop or "—",
        "symbol": symbol or "—",
        "image": f"https://nft.fragment.com/gift/{slug.lower()}-{num}.large.jpg",
        "lottie": f"https://nft.fragment.com/gift/{slug.lower()}-{num}.lottie.json",
        "webp": f"https://nft.fragment.com/gift/{slug.lower()}-{num}.webp",
        "color": stops[0] if stops else (BACKDROPS.get(backdrop.lower()) if backdrop else None),
        "color_edge": stops[1] if len(stops) > 1 else None,
        "pattern_color": flood[0] if flood else "#000000",
        "pattern_url": pat_m.group(1) if pat_m else None,
        "pattern_places": places,
    }
    _cache[key] = (time.time(), data)
    _disk_put(key, data)
    return data


# Цвета фонов (центр) — приблизительно по скриншотам Telegram, можно менять в пульте вручную
BACKDROPS = {
    "burnt sienna": "#c2593a",
    "mustard": "#c78a1b",
    "jade green": "#2f9e72",
    "electric purple": "#8a4fd6",
    "midnight blue": "#2a3f7a",
    "pacific cyan": "#2aa6c4",
    "raspberry": "#c23a6e",
    "cobalt blue": "#2f62c9",
    "copper": "#b4673a",
    "pistachio": "#8bb26a",
    "ivory white": "#d9d5c7",
    "black": "#26282d",
    "silver blue": "#7f93ad",
    "carrot juice": "#d97a22",
    "emerald": "#1f8f5a",
    "english violet": "#5b4a8c",
    "chestnut": "#8c4a2f",
    "grape": "#6d3b8f",
    "rosewood": "#a14a57",
    "pure gold": "#c9a227",
    "onyx black": "#2b2d33",
    "gunmetal": "#4a5260",
    "platinum": "#9aa4b2",
    "satin gold": "#c9a24a",
    "malachite": "#2c8f63",
    "indigo dye": "#2d3f86",
    "navy blue": "#243a73",
    "sky blue": "#4aa3d8",
    "light olive": "#8c9a52",
    "olive green": "#6b7a34",
    "fire engine": "#c63128",
    "pink": "#e07aa6",
    "hunter green": "#2f5d3a",
    "dark lilac": "#7a5aa0",
    "cappuccino": "#9b7358",
    "marine blue": "#1f5a8f",
    "turquoise": "#2fb5b0",
    "tangerine": "#e8832a",
    "lemongrass": "#b8c242",
    "purple": "#7b3fb0",
    "orange": "#e0782a",
    "red": "#c0392b",
    "green": "#2f9e44",
    "blue": "#2f6fd0",
    "yellow": "#d9b72a",
}
