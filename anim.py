"""Анимированная видео-карточка: «поп» карточки, покачивание, искры на кнопке, конфетти. Pillow + ffmpeg."""
import io
import math
import os
import random
import subprocess

from PIL import Image, ImageDraw

import render as rnd

W, H = rnd.W, rnd.H
FPS, SECONDS = 24, 5
OUT_W, OUT_H = 720, 1280  # H.264 yuv420p, чётные размеры


def _ease_pop(t):
    """Пружинный «поп»: 0.3 -> 1 с лёгким перелётом."""
    if t >= 1:
        return 1.0
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _card_box(base):
    """Находит прямоугольник карточки+плашки (блок по центру) сравнением с чистым фоном."""
    from PIL import ImageChops
    return ImageChops.difference(base.convert("RGB"), rnd.chat_background(False)).convert("L").point(lambda v: 255 if v > 30 else 0).getbbox()


def make_video(kind, **kw) -> bytes:
    kw = dict(kw)
    kw.setdefault("mock_mark", True)
    bg_kind = kw.get("bg", "dark")
    png = rnd.render(kind, **kw)
    full = Image.open(io.BytesIO(png)).convert("RGB")
    empty = rnd.chat_background(bg_kind == "light", kw.get("bg_custom") if bg_kind == "custom" else None).convert("RGB")
    from PIL import ImageChops
    box = ImageChops.difference(full, empty).convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not box:
        box = (0, 0, W, H)
    pad = 20
    box = (max(0, box[0] - pad), max(0, box[1] - pad), min(W, box[2] + pad), min(H, box[3] + pad))
    K = OUT_W / W  # 0.6667
    block = full.crop(box).convert("RGBA")
    block = block.resize((int(block.width * K), int(block.height * K)), Image.LANCZOS)
    empty = empty.resize((OUT_W, OUT_H), Image.LANCZOS)
    bw, bh = block.size
    cx, cy = (box[0] + box[2]) / 2 * K, (box[1] + box[3]) / 2 * K
    box = tuple(int(v * K) for v in box)

    rnd_ = random.Random(3)
    cols = [(255, 210, 63), (238, 66, 102), (59, 206, 172), (14, 173, 105), (90, 169, 255), (255, 255, 255)]
    parts = []
    for i in range(170):
        a = rnd_.random() * math.tau
        s = (14 + rnd_.random() * 30) * K
        parts.append([cx, cy, math.cos(a) * s, math.sin(a) * s - 12, 6 + rnd_.random() * 8, 4 + rnd_.random() * 7,
                      rnd_.random() * 6, (rnd_.random() - .5) * .5, cols[i % len(cols)]])

    n = FPS * SECONDS
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
        "-framerate", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-crf", "23", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    import threading
    chunks = []
    reader = threading.Thread(target=lambda: chunks.append(ff.stdout.read()), daemon=True)
    reader.start()

    for f in range(n):
        t = f / FPS
        frame = empty.copy().convert("RGBA")
        k = _ease_pop(min(1, t / 0.7))
        sc = 0.3 + 0.7 * k
        sway = math.sin(t * 2.2) * 0.6 if t > 0.7 else 0
        bob = math.sin(t * 2.0) * 3 if t > 0.7 else 0
        b = block.resize((max(2, int(bw * sc)), max(2, int(bh * sc))), Image.BILINEAR)
        alpha = min(1, t / 0.25)
        if sway:
            b = b.rotate(sway, resample=Image.BILINEAR, expand=True)
        if alpha < 1:
            b.putalpha(b.getchannel("A").point(lambda v: int(v * alpha)))
        frame.alpha_composite(b, (int(cx - b.width / 2), int(cy - b.height / 2 + bob)))
        d = ImageDraw.Draw(frame, "RGBA")
        if t > 0.7:
            by = box[3] - 100
            for j, (ox, oy) in enumerate(((-80, -7), (73, 13), (93, -13), (-40, 17))):
                tw = max(0, math.sin(t * 5 + j * 1.7))
                r = 3 + 8 * tw
                x, y = cx + ox, by + oy
                d.polygon([(x, y - r), (x + r * .25, y - r * .25), (x + r, y), (x + r * .25, y + r * .25),
                           (x, y + r), (x - r * .25, y + r * .25), (x - r, y), (x - r * .25, y - r * .25)],
                          fill=(255, 255, 255, int(230 * tw)))
        ct = t - 0.15
        if 0 <= ct < 3:
            fade = 1 - ct / 3
            for p in parts:
                x = p[0] + p[2] * ct * 1.2
                y = p[1] + p[3] * ct * 1.2 + 0.5 * 55 * ct * ct * 3 * K
                ang = p[6] + p[7] * ct * 24
                dx, dy = math.cos(ang) * p[4] * K / 2, math.sin(ang) * p[5] * K / 2
                d.polygon([(x - dx - dy, y - dy + dx), (x + dx - dy, y + dy + dx), (x + dx + dy, y + dy - dx), (x - dx + dy, y - dy - dx)],
                          fill=p[8] + (int(255 * fade),))
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close()
    reader.join()
    ff.wait()
    return chunks[0]


def _firework(rng, cx, cy, t0, cols):
    """Один залп: искры разлетаются из точки (cx, cy) начиная с момента t0."""
    sparks = []
    for i in range(46):
        a = rng.random() * math.tau
        sp = 120 + rng.random() * 230
        sparks.append((cx, cy, math.cos(a) * sp, math.sin(a) * sp, cols[i % len(cols)], t0))
    return sparks


def make_gift_video(nft: dict, sender: str, color: str = None, button_text: str = "Посмотреть") -> bytes:
    """Ролик «получение подарка»: плашка + настоящая карточка (как в Telegram) выпрыгивает, залпы фейерверков и конфетти."""
    card = Image.open(io.BytesIO(rnd.card_only(nft, sender=sender, color=color, button_text=button_text, width=520))).convert("RGBA")
    bg = rnd.chat_background(False).convert("RGB").resize((OUT_W, OUT_H), Image.LANCZOS).convert("RGBA")
    pill_png = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    rnd.pill(pill_png, f"{sender} передал(а) Вам подарок!", 60, False)
    pill_bb = pill_png.getchannel("A").getbbox()
    pill = pill_png.crop(pill_bb) if pill_bb else pill_png
    k = OUT_W * 0.9 / max(pill.width, 1)
    k = min(k, 0.67)
    pill = pill.resize((max(1, int(pill.width * k)), max(1, int(pill.height * k))), Image.LANCZOS)

    cx = OUT_W // 2
    total_h = pill.height + 24 + card.height
    top = (OUT_H - total_h) // 2
    pill_y = top
    card_cy = top + pill.height + 24 + card.height // 2

    rng = random.Random(7)
    cols = [(255, 210, 63), (238, 66, 102), (59, 206, 172), (90, 169, 255), (255, 255, 255), (255, 140, 66)]
    bursts = []
    for t0, bx, by in ((0.5, 150, 330), (1.0, 570, 280), (1.5, 360, 220), (2.2, 190, 900), (2.7, 540, 940)):
        bursts += _firework(rng, bx, by, t0, cols)
    conf = []
    for i in range(190):
        a = rng.random() * math.tau
        s = 260 + rng.random() * 520
        conf.append([cx, card_cy, math.cos(a) * s, math.sin(a) * s - 380, 8 + rng.random() * 8, 5 + rng.random() * 7,
                     rng.random() * 6, (rng.random() - .5) * 14, cols[i % len(cols)]])

    seconds = 5
    n = FPS * seconds
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
        "-framerate", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-crf", "23", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    import threading
    chunks = []
    reader = threading.Thread(target=lambda: chunks.append(ff.stdout.read()), daemon=True)
    reader.start()

    for f in range(n):
        t = f / FPS
        frame = bg.copy()
        # плашка появляется сразу
        pa = min(1, t / 0.3)
        p = pill.copy()
        if pa < 1:
            p.putalpha(p.getchannel("A").point(lambda v: int(v * pa)))
        frame.alpha_composite(p, (cx - p.width // 2, pill_y))
        # карточка: пружинный выход после 0.25 c
        ct = max(0.0, t - 0.25)
        kk = _ease_pop(min(1, ct / 0.7))
        sc = 0.25 + 0.75 * kk
        if t >= 0.25:
            c = card.resize((max(2, int(card.width * sc)), max(2, int(card.height * sc))), Image.BILINEAR)
            al = min(1, ct / 0.25)
            if al < 1:
                c.putalpha(c.getchannel("A").point(lambda v: int(v * al)))
            frame.alpha_composite(c, (cx - c.width // 2, card_cy - c.height // 2))
        d = ImageDraw.Draw(frame, "RGBA")
        # фейерверки
        for (x0, y0, vx, vy, col, t0) in bursts:
            bt = t - t0
            if 0 <= bt < 1.3:
                fade = 1 - bt / 1.3
                x = x0 + vx * bt * 0.8
                y = y0 + vy * bt * 0.8 + 90 * bt * bt
                r = 3.5 * fade + 1
                d.ellipse([x - r, y - r, x + r, y + r], fill=col + (int(255 * fade),))
                x2, y2 = x - vx * 0.03, y - vy * 0.03
                d.line([(x, y), (x2, y2)], fill=col + (int(160 * fade),), width=2)
        # конфетти от карточки
        cft = t - 0.4
        if 0 <= cft < 3.2:
            fade = 1 - cft / 3.2
            for q in conf:
                x = q[0] + q[2] * cft
                y = q[1] + q[3] * cft + 420 * cft * cft
                ang = q[6] + q[7] * cft
                dx, dy = math.cos(ang) * q[4] / 2, math.sin(ang) * q[5] / 2
                d.polygon([(x - dx - dy, y - dy + dx), (x + dx - dy, y + dy + dx), (x + dx + dy, y + dy - dx), (x - dx + dy, y - dy - dx)],
                          fill=q[8] + (int(255 * fade),))
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close()
    reader.join()
    ff.wait()
    return chunks[0]
