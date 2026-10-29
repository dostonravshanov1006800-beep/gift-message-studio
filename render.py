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
    d.rounded_rectangle([x0, y, x0 + pw, y + ph], ph / 2 if len(lines) == 1 else 36,
                        fill=(0, 0, 0, 120) if not light else (60, 80, 60, 150))
    for i, l in enumerate(lines):
        d.text((W / 2, y + 13 + lh * i + lh / 2), l, font=f, fill="white", anchor="mm")
    return y + ph


def fetch_image(url: str):
    try:
        r = httpx.get(url, timeout=8, follow_redirects=True)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
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
    d.rounded_rectangle([0, 0, cw, ch], 48, fill=(10, 20, 28, 150))
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


def nft_card(img, y, nft: dict, sender: str, color_hex: str, button_text="Посмотреть"):
    cw, ch = int(W * 0.66), 1040
    x0 = (W - cw) // 2
    base = hex_rgb(color_hex)
    card = Image.new("RGBA", (cw, ch), base + (255,))
    # мягкая радиальная заливка
    grad = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(40):
        t = i / 40
        c = tuple(int(base[k] + (lighter(base, 1.3)[k] - base[k]) * (1 - t)) for k in range(3)) + (int(200 * (1 - t) / 2),)
        r = int(cw * 0.8 * (1 - t) + 20)
        gd.ellipse([cw / 2 - r, 330 - r, cw / 2 + r, 330 + r], fill=c)
    card = Image.alpha_composite(card, grad.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(card, "RGBA")
    # узор шахматкой
    pat = lighter(base, 1.35) + (70,)
    for gy in range(40, ch, 100):
        for gx in range(30, cw, 100):
            x = gx + (50 if (gy // 100) % 2 else 0)
            d.ellipse([x, gy, x + 26, gy + 26], fill=pat)
    # изображение модели
    pic = fetch_image(nft.get("image", ""))
    if pic is None:
        pic = fetch_image(nft.get("webp", ""))
    if pic:
        pic = pic.resize((400, 400))
        card.paste(pic, ((cw - 400) // 2, 130), pic)
    else:
        d.ellipse([cw / 2 - 150, 180, cw / 2 + 150, 480], fill=(255, 255, 255, 60))
    # заголовок
    d.text((cw / 2, 610), f"Подарок от {sender}", font=font(46, True), fill="white", anchor="mm")
    num = f"{nft['number']:,}"
    d.text((cw / 2, 668), f"{nft['title']} #{num}", font=font(36), fill=(255, 255, 255, 180), anchor="mm")
    # три строки
    rows = [("Модель", nft["model"]), ("Фон", nft["backdrop"]), ("Узор", nft["symbol"])]
    ry = 750
    lf, vf = font(34), font(34, True)
    for lab, val in rows:
        d.text((cw / 2 - 20, ry), lab, font=lf, fill=(255, 255, 255, 170), anchor="rm")
        d.text((cw / 2 + 20, ry), val, font=vf, fill="white", anchor="lm")
        ry += 56
    # кнопка
    bw, bh = 340, 92
    bx, by = (cw - bw) // 2, ch - bh - 36
    d.rounded_rectangle([bx, by, bx + bw, by + bh], bh // 2, fill=darker(base, 0.65) + (230,))
    d.text((cw / 2, by + bh / 2), button_text, font=font(40, True), fill="white", anchor="mm")
    # лента «подарок»
    ribbon = Image.new("RGBA", (260, 60), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon)
    rd.rectangle([0, 0, 260, 60], fill=darker(base, 0.7) + (230,))
    rd.text((130, 30), "подарок", font=font(30, True), fill="white", anchor="mm")
    ribbon = ribbon.rotate(-45, expand=True, resample=Image.BICUBIC)
    card.paste(ribbon, (cw - ribbon.width + 40, -30), ribbon)
    # скругление
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], 48, fill=255)
    card.putalpha(mask)
    img.paste(card, (x0, y), card)
    return y + ch


def render(kind: str, *, sender="Неизвестный пользователь", stars=75, ton="0,83", usd="1,12",
           nft=None, color=None, banner=None, date_label=None, mock_mark=True,
           bg="dark", bg_custom=None, button_text="Посмотреть") -> bytes:
    light = bg == "light"
    img = chat_background(light, bg_custom if bg == "custom" else None)
    d = ImageDraw.Draw(img, "RGBA")

    if kind == "stars":
        text = banner or f"{sender} отправил(а) Вам подарок стоимостью {ton} TON (~ {usd} $)"
        total = 150 + 860
        y = (H - total) // 2
        y = pill(img, text, y, light) + 36
        star_gift_card(img, y, stars)
    else:
        text = banner or f"{sender} передал(а) Вам подарок!"
        total = 150 + 1040 + (110 if date_label else 0)
        y = (H - total) // 2
        if date_label:
            y = pill(img, date_label, y, light) + 30
        y = pill(img, text, y, light) + 36
        color = color or (nft or {}).get("color") or "#c2593a"
        nft_card(img, y, nft, sender, color, button_text)

    if mock_mark:
        d.text((W - 40, H - 36), "МАКЕТ", font=font(28, True), fill=(255, 255, 255, 140), anchor="rb")

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
