"""Рисует макет «подарок» в стиле Telegram (тёмная тема) в PNG. Только Pillow, без браузера."""
import io
import math
import random
import colorsys
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920  # 9:16
FONT_PATHS = [
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-{w}.ttf",
    "/usr/share/fonts/truetype/roboto/Roboto-{w}.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans{b}.ttf",
]


def font(size: int, bold=False):
    w = "Bold" if bold else "Regular"
    b = "-Bold" if bold else ""
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p.format(w=w, b=b), size)
        except Exception:
            continue
    return ImageFont.load_default()


def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def darker(rgb, k=0.7):
    r, g, b = [x / 255 for x in rgb]
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hh, max(0, l * k), s)
    return (int(r * 255), int(g * 255), int(b * 255))


def lighter(rgb, k=1.25):
    r, g, b = [x / 255 for x in rgb]
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hh, min(1, l * k), s)
    return (int(r * 255), int(g * 255), int(b * 255))


def chat_background(light=False, custom=None):
    base = hex_rgb(custom) if custom else ((222, 232, 214) if light else (20, 30, 40))
    img = Image.new("RGB", (W, H), base)
    # мягкие цветные «блики» под стеклом
    glow = Image.new("RGB", (W, H), base)
    gd = ImageDraw.Draw(glow)
    for (gx, gy, rad, col) in ((200, 300, 520, (59, 130, 246)), (900, 700, 480, (168, 85, 247)),
                               (300, 1500, 560, (236, 72, 153)), (880, 1700, 420, (6, 182, 212))):
        gd.ellipse([gx - rad, gy - rad, gx + rad, gy + rad], fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    img = Image.blend(img, glow, 0.45 if not light else 0.25)
    d = ImageDraw.Draw(img, "RGBA")
    rnd = random.Random(7)
    icon = (255, 255, 255, 14) if not light else (0, 0, 0, 14)
    # узор из контурных иконок (кружки, звёзды, облака) — низкий контраст
    for gy in range(0, H, 120):
        for gx in range(0, W, 120):
            x = gx + rnd.randint(-14, 14) + (60 if (gy // 120) % 2 else 0)
            y = gy + rnd.randint(-14, 14)
            t = rnd.randint(0, 3)
            if t == 0:
                d.ellipse([x, y, x + 36, y + 36], outline=icon, width=3)
            elif t == 1:
                pts = []
                for i in range(10):
                    r = 20 if i % 2 == 0 else 9
                    a = math.pi / 5 * i - math.pi / 2
                    pts.append((x + 18 + r * math.cos(a), y + 18 + r * math.sin(a)))
                d.polygon(pts, outline=icon)
            elif t == 2:
                d.rounded_rectangle([x, y + 6, x + 40, y + 30], 10, outline=icon, width=3)
            else:
                d.arc([x, y, x + 40, y + 40], 200, 340, fill=icon, width=3)
    return img


def glass_panel(img, box, radius, light=False, tint=(255, 255, 255)):
    """Liquid glass: размытие фона под панелью + светлая подложка + блик и светлая кромка."""
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    region = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(22))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius, fill=255)
    overlay = Image.new("RGBA", (w, h), tint + (38 if not light else 90,))
    # диагональный блик
    hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    for i in range(h):
        a = int(70 * max(0, 1 - i / (h * 0.55)))
        hd.line([(0, i), (w, i)], fill=(255, 255, 255, a))
    region = Image.alpha_composite(region.convert("RGBA"), overlay)
    region = Image.alpha_composite(region, hl)
    ed = ImageDraw.Draw(region)
    ed.rounded_rectangle([0, 0, w - 1, h - 1], radius, outline=(255, 255, 255, 110), width=2)
    ed.rounded_rectangle([3, 3, w - 4, h - 4], max(1, radius - 3), outline=(255, 255, 255, 40), width=1)
    img.paste(region.convert("RGB"), (x0, y0), mask)


def pill(img, text, y, light=False):
    d = ImageDraw.Draw(img, "RGBA")
    f = font(34, False)
    # перенос по ширине
    maxw = int(W * 0.86)
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= maxw - 70:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    lh = 46
    tw = max(d.textlength(l, font=f) for l in lines)
    pw, ph = tw + 70, lh * len(lines) + 26
    x0 = (W - pw) / 2
    rad = int(ph / 2 if len(lines) == 1 else 36)
    glass_panel(img, [x0, y, x0 + pw, y + ph], rad, light)
    d = ImageDraw.Draw(img, "RGBA")
    for i, l in enumerate(lines):
        d.text((W / 2, y + 13 + lh * i + lh / 2), l, font=f, fill="white", anchor="mm")
    return y + ph


def fetch_image(url: str):
    """Скачивает картинку (2 попытки) и кэширует на диск на 24 часа: работает и при кратком сбое сети."""
    import hashlib, os, time
    if not url:
        return None
    os.makedirs("cache/img", exist_ok=True)
    path = os.path.join("cache/img", hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 86400:
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    for _ in range(2):
        try:
            r = httpx.get(url, timeout=8, follow_redirects=True)
            if r.status_code == 200:
                open(path, "wb").write(r.content)
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception:
            continue
    if os.path.exists(path):  # устаревший кэш лучше, чем пустота
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return None


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def star_gift_card(img, y, stars: int, sparkle=True):
    cw, ch = int(W * 0.66), 860
    x0 = (W - cw) // 2
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    glass_panel(img, [x0, y, x0 + cw, y + ch], 48)
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(card, "RGBA")
    # коробка со звездой (векторный рисунок)
    cx, cy = cw // 2, 300
    d.polygon([(cx - 150, cy), (cx + 150, cy), (cx + 120, cy + 190), (cx - 120, cy + 190)], fill=(70, 160, 60))
    d.polygon([(cx - 150, cy), (cx - 100, cy - 50), (cx + 100, cy - 50), (cx + 150, cy)], fill=(100, 190, 80))
    d.rectangle([cx - 24, cy - 50, cx + 24, cy + 190], fill=(255, 190, 40))
    d.rectangle([cx - 150, cy + 60, cx + 150, cy + 100], fill=(255, 190, 40))
    pts = []
    for i in range(10):
        r = 120 if i % 2 == 0 else 52
        a = math.pi / 5 * i - math.pi / 2
        pts.append((cx + r * math.cos(a), cy - 120 + r * math.sin(a)))
    d.polygon(pts, fill=(255, 205, 40), outline=(255, 230, 120))
    d.text((cw / 2, 540), f"{stars} звёзд", font=font(56, True), fill="white", anchor="mm")
    desc = "Используйте звёзды, чтобы открывать контент и получать услуги в Telegram."
    f = font(36)
    ty = 610
    for l in wrap(d, desc, f, cw - 110):
        d.text((cw / 2, ty), l, font=f, fill=(220, 230, 236, 235), anchor="mm")
        ty += 50
    # кнопка
    bw, bh = 330, 92
    bx, by = (cw - bw) // 2, ch - bh - 40
    d.rounded_rectangle([bx, by, bx + bw, by + bh], bh // 2, fill=(70, 100, 150, 200))
    d.text((cw / 2, by + bh / 2), "Посмотреть", font=font(40, True), fill="white", anchor="mm")
    if sparkle:
        for sx, sy in ((bx + 40, by + 20), (bx + bw - 50, by + bh - 24), (bx + bw - 20, by + 18)):
            d.polygon([(sx, sy - 14), (sx + 4, sy - 4), (sx + 14, sy), (sx + 4, sy + 4), (sx, sy + 14), (sx - 4, sy + 4), (sx - 14, sy), (sx - 4, sy - 4)], fill=(255, 255, 255, 220))
    img.paste(card, (x0, y), card)
    return y + ch


def _own_image(nft):
    """Картинка, загруженная пользователем (base64 data-URL или сырые байты) — без сети."""
    import base64
    raw = nft.get("image_b64")
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            raw = base64.b64decode(raw.split(",", 1)[-1])
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        bbox = im.getbbox()
        return im.crop(bbox) if bbox else im
    except Exception:
        return None


def _emoji_pattern(card, cw, ch, emoji, color=(0, 0, 0), strength=0.22):
    """Узор из символа (эмодзи/буква) по сетке вокруг подарка — когда нет файла узора."""
    f = font(70, True)
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for gy, row in enumerate(range(60, ch - 200, 150)):
        for gx in range(40 + (75 if gy % 2 else 0), cw, 150):
            ld.text((gx, row), emoji, font=f, fill=color + (int(255 * strength),), anchor="mm")
    card.alpha_composite(layer)


def nft_card(img, y, nft: dict, sender: str, color_hex: str, button_text="Посмотреть"):
    cw, ch = int(W * 0.66), 1040
    x0 = (W - cw) // 2
    c_center = hex_rgb(color_hex)
    c_edge = hex_rgb(nft.get("color_edge") or "#000000") if nft.get("color_edge") else darker(c_center, 0.8)
    base = c_center
    # радиальный градиент центр -> край (как в SVG страницы)
    card = Image.new("RGBA", (cw, ch), c_edge + (255,))
    steps = 60
    gd = ImageDraw.Draw(card)
    for i in range(steps):
        t = i / (steps - 1)
        c = tuple(int(c_center[k] + (c_edge[k] - c_center[k]) * t) for k in range(3))
        rx, ry = cw * 0.9 * (1 - t) + 4, ch * 0.62 * (1 - t) + 4
        gd.ellipse([cw / 2 - rx, ch * 0.34 - ry, cw / 2 + rx, ch * 0.34 + ry], fill=c + (255,))
    # настоящий узор: иконка со страницы t.me на тех же позициях, цвет из flood-color
    pat_img = fetch_image(nft.get("pattern_url") or "")
    places = nft.get("pattern_places") or []
    if pat_img is not None and places:
        alpha_src = pat_img.getchannel("A")
        tint = hex_rgb(nft.get("pattern_color") or "#000000")
        sx = cw / 420.0
        for op, px, py, sc in places:
            size = max(4, int(100 * sc * sx))
            ic = Image.new("RGBA", (size, size), tint + (0,))
            a_ch = alpha_src.resize((size, size), Image.LANCZOS).point(lambda v, o=op: int(v * min(1, o * 1.6)))
            ic.putalpha(a_ch)
            card.alpha_composite(ic, (int(px * sx), int(py * sx * 1.0)))
    if (nft.get("pattern_text") and not places):
        _emoji_pattern(card, cw, ch, nft["pattern_text"][:2], hex_rgb(nft.get("pattern_color") or "#000000"))
    d = ImageDraw.Draw(card, "RGBA")
    # фото подарка (Fragment): large.jpg, затем webp; если нет, рисуем крупную первую букву вместо пустого круга
    pic = _own_image(nft) or fetch_image(nft.get("image", "")) or fetch_image(nft.get("webp", ""))
    if pic:
        pic = pic.resize((420, 420), Image.LANCZOS)
        card.paste(pic, ((cw - 420) // 2, 120), pic if pic.mode == "RGBA" else None)
    else:
        d.text((cw / 2, 330), (nft.get("title") or "?")[0], font=font(220, True), fill=(255, 255, 255, 200), anchor="mm")
    d.text((cw / 2, 610), f"Подарок от {sender}", font=font(46, True), fill="white", anchor="mm")
    num = nft.get("number")
    sub = f"{nft['title']} #{int(num):,}" if str(num or "").strip().isdigit() and int(num) > 0 else str(nft["title"])
    d.text((cw / 2, 668), sub, font=font(36), fill=(255, 255, 255, 180), anchor="mm")
    rows = [("Модель", nft["model"]), ("Фон", nft["backdrop"]), ("Узор", nft["symbol"])]
    ry = 750
    lf, vf = font(34), font(34, True)
    for lab, val in rows:
        d.text((cw / 2 - 20, ry), lab, font=lf, fill=(255, 255, 255, 170), anchor="rm")
        d.text((cw / 2 + 20, ry), val, font=vf, fill="white", anchor="lm")
        ry += 56
    bw, bh = 340, 92
    bx, by = (cw - bw) // 2, ch - bh - 36
    d.rounded_rectangle([bx, by, bx + bw, by + bh], bh // 2, fill=darker(base, 0.65) + (230,))
    d.text((cw / 2, by + bh / 2), button_text, font=font(40, True), fill="white", anchor="mm")
    ribbon = Image.new("RGBA", (260, 60), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon)
    rd.rectangle([0, 0, 260, 60], fill=darker(base, 0.7) + (230,))
    rd.text((130, 30), "подарок", font=font(30, True), fill="white", anchor="mm")
    ribbon = ribbon.rotate(-45, expand=True, resample=Image.BICUBIC)
    card.paste(ribbon, (cw - ribbon.width + 40, -30), ribbon)
    hl = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    for i in range(int(ch * 0.5)):
        hd.line([(0, i), (cw, i)], fill=(255, 255, 255, int(55 * (1 - i / (ch * 0.5)))))
    card = Image.alpha_composite(card, hl)
    ImageDraw.Draw(card).rounded_rectangle([1, 1, cw - 2, ch - 2], 48, outline=(255, 255, 255, 120), width=3)
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], 48, fill=255)
    card.putalpha(mask)
    img.paste(card, (x0, y), card)
    return y + ch


def _compose(kind, y0, img, sender, stars, ton, usd, nft, color, banner, date_label, button_text, light):
    """Рисует блок (дата + плашка + карточка) начиная с y0, возвращает нижнюю границу."""
    if kind == "stars":
        text = banner or f"{sender} отправил(а) Вам подарок стоимостью {ton} TON (~ {usd} $)"
        y = pill(img, text, y0, light) + 36
        return star_gift_card(img, y, stars)
    text = banner or f"{sender} передал(а) Вам подарок!"
    y = y0
    if date_label:
        y = pill(img, date_label, y, light) + 30
    y = pill(img, text, y, light) + 36
    color = color or (nft or {}).get("color") or "#c2593a"
    return nft_card(img, y, nft, sender, color, button_text)


def render(kind: str, *, sender="Неизвестный пользователь", stars=75, ton="0,83", usd="1,12",
           nft=None, color=None, banner=None, date_label=None, mock_mark=True,
           bg="dark", bg_custom=None, button_text="Посмотреть") -> bytes:
    light = bg == "light"
    args = (sender, stars, ton, usd, nft, color, banner, date_label, button_text, light)
    # 1) замеряем реальную высоту блока на пробном холсте
    probe = Image.new("RGB", (W, H * 2), (0, 0, 0))
    block_h = _compose(kind, 0, probe, *args)
    # 2) ставим блок так, чтобы его центр был ровно в центре кадра
    y0 = (H - block_h) // 2
    img = chat_background(light, bg_custom if bg == "custom" else None)
    _compose(kind, y0, img, *args)
    if mock_mark:
        ImageDraw.Draw(img, "RGBA").text((W - 40, H - 36), "МАКЕТ", font=font(28, True),
                                         fill=(255, 255, 255, 140), anchor="rb")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
