"""Kapanış kartı: beğen / abone ol / zil, imleç sırayla tıklar (aiavatarilevideo/engine.py'den uyarlandı)."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import ROOT

DUR = 3.6
CLICK_LIKE, CLICK_SUB, CLICK_BELL = 0.8, 1.7, 2.5  # kart başlangıcına göre
FONT = str(ROOT / 'fonts' / 'LuckiestGuy-Regular.ttf')
_fonts = {}


def font(sz):
    if sz not in _fonts:
        _fonts[sz] = ImageFont.truetype(FONT, sz)
    return _fonts[sz]


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, k):
    return a + (b - a) * k


def circ(d, c, r, fill, outline=None, width=1):
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=fill, outline=outline, width=width)


def icon_like(d, cx, cy, s, col):
    def P(x, y):
        return (cx + (x - 32) * s, cy + (y - 34) * s)
    d.rounded_rectangle((*P(4, 28), *P(16, 62)), radius=int(3 * s), fill=col)
    d.rounded_rectangle((*P(20, 26), *P(58, 62)), radius=int(8 * s), fill=col)
    d.polygon([P(20, 30), P(30, 4), P(40, 8), P(38, 28)], fill=col)
    circ(d, P(35, 8), 5.5 * s, col)


def icon_bell(d, cx, cy, s, col, ang=0.0):
    def P(x, y):
        x, y = x * s, y * s
        c, sn = math.cos(ang), math.sin(ang)
        return (cx + x * c - (y + 30 * s) * sn, cy + x * sn + (y + 30 * s) * c - 30 * s)
    pts = [P(-28, 18), P(-22, 12), P(-20, -10)] + \
          [P(20 * math.cos(a), -10 - 18 * math.sin(a)) for a in np.linspace(math.pi, 0, 10)] + \
          [P(20, -10), P(22, 12), P(28, 18)]
    d.polygon(pts, fill=col)
    circ(d, P(0, 26), 7 * s, col)
    circ(d, P(0, -30), 4 * s, col)


def cursor(d, x, y, press):
    s = 1.6 * (0.85 if press else 1.0)
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    d.polygon([(x + px * s, y + py * s) for px, py in pts], fill=(255, 255, 255), outline=(20, 20, 20), width=3)


def layer(W, lt, tagline):
    """lt: kart başlangıcından beri geçen süre -> (RGBA katman W x 420, katmanın ekrandaki y ofseti)."""
    Hh = 420
    img = Image.new('RGBA', (W, Hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = ease_out(lt / 0.35)
    cy = 190 - (1 - k) * 120
    d.rounded_rectangle((60, cy - 120, W - 60, cy + 140), radius=40, fill=(12, 18, 36, int(250 * k)),
                        outline=(255, 255, 255, int(60 * k)), width=3)
    liked, subbed, belled = lt >= CLICK_LIKE, lt >= CLICK_SUB, lt >= CLICK_BELL
    lx, bx, sx = 180, W - 180, W / 2
    # beğen
    circ(d, (lx, cy - 10), 62, (255, 255, 255, int(255 * k)) if liked else (255, 255, 255, int(40 * k)))
    icon_like(d, lx, cy - 10, 1.35, (235, 70, 90) if liked else (255, 255, 255, int(255 * k)))
    if liked and lt - CLICK_LIKE < 0.6:
        u = (lt - CLICK_LIKE) / 0.6
        d.text((lx + 40, cy - 90 - 60 * u), '+1', font=font(40), fill=(255, 255, 255, int(255 * (1 - u))))
        circ(d, (lx, cy - 10), 62 + 50 * u, None, outline=(255, 255, 255, int(200 * (1 - u))), width=5)
    # abone ol
    sw = 380
    pc = (90, 90, 90) if subbed else (225, 35, 35)
    d.rounded_rectangle((sx - sw / 2, cy - 55, sx + sw / 2, cy + 35), radius=45, fill=pc + (int(255 * k),))
    d.text((sx, cy - 10), 'SUBSCRIBED' if subbed else 'SUBSCRIBE', font=font(40), fill=(255, 255, 255, int(255 * k)),
           anchor='mm')
    if subbed and lt - CLICK_SUB < 0.5:
        u = (lt - CLICK_SUB) / 0.5
        d.rounded_rectangle((sx - sw / 2 - 30 * u, cy - 55 - 30 * u, sx + sw / 2 + 30 * u, cy + 35 + 30 * u),
                            radius=60, outline=(255, 255, 255, int(200 * (1 - u))), width=5)
    # zil
    ang = 0.35 * math.sin((lt - CLICK_BELL) * 30) * math.exp(-(lt - CLICK_BELL) * 3) if belled else 0
    circ(d, (bx, cy - 10), 62, (255, 255, 255, int(40 * k)) if not belled else (255, 205, 80, int(255 * k)))
    icon_bell(d, bx, cy - 12, 1.2, (255, 255, 255, int(255 * k)) if not belled else (60, 40, 20), ang)
    if belled and lt - CLICK_BELL < 0.6:
        u = (lt - CLICK_BELL) / 0.6
        for a in (-0.9, -0.5, 0.5, 0.9):
            r1, r2 = 80 + 20 * u, 100 + 25 * u
            d.line([(bx + math.sin(a) * r1, cy - 10 - math.cos(a) * r1),
                    (bx + math.sin(a) * r2, cy - 10 - math.cos(a) * r2)],
                   fill=(255, 220, 120, int(255 * (1 - u))), width=6)
    d.text((W / 2, cy + 95), tagline, font=font(36), fill=(255, 225, 90, int(235 * k)), anchor='mm')
    # imleç
    keys = [(0.35, (W + 60, cy + 200)), (CLICK_LIKE - 0.05, (lx + 10, cy + 10)), (CLICK_LIKE + 0.25, (lx + 10, cy + 10)),
            (CLICK_SUB - 0.05, (sx + 60, cy)), (CLICK_SUB + 0.2, (sx + 60, cy)), (CLICK_BELL - 0.05, (bx + 10, cy + 10)),
            (CLICK_BELL + 0.4, (bx + 10, cy + 10)), (CLICK_BELL + 0.9, (W + 80, cy + 260))]
    if lt >= keys[0][0]:
        pos = keys[-1][1]
        for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
            if t0 <= lt < t1:
                u = ease((lt - t0) / (t1 - t0))
                pos = (lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u))
                break
        press = any(0 <= lt - c < 0.12 for c in (CLICK_LIKE, CLICK_SUB, CLICK_BELL))
        cursor(d, pos[0], pos[1], press)
    return img
