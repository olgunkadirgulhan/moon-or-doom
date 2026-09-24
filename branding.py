"""Moon or Doom kanal görselleri: banner (2560x1440), profil (800x800), filigran (150x150) -> branding/

    python branding.py
"""
import math
import random
import sys
from pathlib import Path

import cairo
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stickcoin import rig  # noqa: E402
from stickcoin.chart import DOWN, UP  # noqa: E402
from stickcoin.render import pil_to_surface, text_block  # noqa: E402

OUT = HERE / 'branding'
NAVY = (0.06, 0.09, 0.17)


def character(ctx, cid, x, ground, s, facing, emotion, pose, mouth='closed', hf=None):
    st = dict(rig.pose_targets(pose))
    if hf:
        st['hf'] = hf
    st.update(emotion=emotion, mouth=mouth, t=0.2, breath=1.0, bend=st.get('bend', 'out'))
    return rig.draw(ctx, cid, x, ground, s, facing, st)


def paste_text(ctx, words, size, cx, cy, maxw, color=(255, 255, 255), stroke_w=None):
    surf = pil_to_surface(text_block(words, size, maxw, color=color, stroke_w=stroke_w or max(4, size // 9)))
    ctx.set_source_surface(surf, cx - surf.get_width() / 2, cy - surf.get_height() / 2)
    ctx.paint()


def candles(ctx, x0, x1, y_mid, n, trend, h, rnd, width_k=0.62):
    """Temsili mum dizisi: trend > 0 yükselen, < 0 düşen."""
    cw = (x1 - x0) / n
    price = 0.0
    for i in range(n):
        o = price
        c = o + trend * h / n * rnd.uniform(0.3, 2.2) + rnd.uniform(-h / n, h / n) * 0.9
        hi, lo = max(o, c) + rnd.uniform(0, h / n), min(o, c) - rnd.uniform(0, h / n)
        x = x0 + (i + 0.5) * cw
        col = UP if c >= o else DOWN
        ctx.set_source_rgb(*col)
        ctx.set_line_width(max(3, cw * 0.1))
        ctx.move_to(x, y_mid - hi); ctx.line_to(x, y_mid - lo); ctx.stroke()
        top, bot = y_mid - max(o, c), y_mid - min(o, c)
        ctx.rectangle(x - cw * width_k / 2, top, cw * width_k, max(4, bot - top)); ctx.fill()
        price = c


def split_bg(ctx, W, H, angle=0.18):
    """Solda yeşil (moon), sağda kırmızı (doom) çapraz bölünmüş zemin."""
    ctx.set_source_rgb(*NAVY); ctx.paint()
    g = cairo.LinearGradient(0, 0, W, 0)
    g.add_color_stop_rgba(0, 0.05, 0.45, 0.25, 0.9)
    g.add_color_stop_rgba(0.48, 0.05, 0.3, 0.2, 0.35)
    g.add_color_stop_rgba(0.52, 0.35, 0.05, 0.08, 0.35)
    g.add_color_stop_rgba(1, 0.6, 0.06, 0.1, 0.9)
    ctx.set_source(g); ctx.paint()
    rnd = random.Random(3)
    for _ in range(int(W * H / 9000)):
        ctx.arc(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1, 3.5), 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, rnd.uniform(0.15, 0.6)); ctx.fill()


def moon(ctx, x, y, r):
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgb(0.97, 0.93, 0.75); ctx.fill()
    for dx, dy, rr in ((-0.3, -0.2, 0.18), (0.25, 0.1, 0.13), (-0.05, 0.35, 0.1)):
        ctx.arc(x + dx * r, y + dy * r, rr * r, 0, 2 * math.pi)
        ctx.set_source_rgb(0.85, 0.8, 0.6); ctx.fill()


def banner():
    W, H = 2560, 1440
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    split_bg(ctx, W, H)
    rnd = random.Random(7)
    # güvenli alan (tüm cihazlar): orta 1546x423 -> x 507..2053, y 508..931
    ctx.push_group()
    candles(ctx, 820, 1250, 900, 14, +1, 300, rnd)
    candles(ctx, 1310, 1740, 600, 14, -1, 300, rnd)
    ctx.pop_group_to_source(); ctx.paint_with_alpha(0.35)
    moon(ctx, 560, 300, 80)
    ground, s = 940, 4.1
    character(ctx, 'moon_max', 680, ground, s, 1, 'excited', 'celebrate', 'wide')
    character(ctx, 'bear_betty', 1880, ground, s, -1, 'smug', 'arms_crossed', 'closed')
    paste_text(ctx, ['MOON', 'OR', 'DOOM'], 150, W / 2, 640, 1500, color=(255, 222, 40))
    paste_text(ctx, "TODAY'S TOP GAINER & LOSER".split(), 50, W / 2, 790, 1000)
    paste_text(ctx, 'EXPLAINED IN 60 SECONDS · 3X DAILY'.split(), 38, W / 2, 855, 1000, color=(200, 215, 240))
    surf.write_to_png(str(OUT / 'banner.png'))


def head_shot(cid, size, emotion='happy', ring=True, split=True):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surf)
    if split:
        split_bg(ctx, size, size)
        rnd = random.Random(5)
        candles(ctx, size * 0.05, size * 0.95, size * 0.95, 9, +1, size * 0.45, rnd)
    s = size / 64
    character(ctx, cid, size / 2 - 3 * s, size / 2 + 79 * s, s, 1, emotion, 'standing', 'closed')
    if ring:
        ctx.arc(size / 2, size / 2, size / 2 - size * 0.02, 0, 2 * math.pi)
        ctx.set_source_rgb(0.08, 0.08, 0.1); ctx.set_line_width(size * 0.035); ctx.stroke()
    return surf


def watermark():
    """150x150 abone ol rozeti: Charlie + küçük kırmızı SUBSCRIBE şeridi."""
    size = 300
    surf = head_shot('charlie', size, 'excited', ring=False)
    ctx = cairo.Context(surf)
    rig.rrect(ctx, 20, size - 88, size - 40, 64, 30)
    ctx.set_source_rgb(0.88, 0.14, 0.14); ctx.fill()
    paste_text(ctx, ['SUBSCRIBE'], 44, size / 2, size - 55, size, stroke_w=0)
    # yuvarlak maske
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    c2 = cairo.Context(out)
    c2.arc(size / 2, size / 2, size / 2 - 2, 0, 2 * math.pi); c2.clip()
    c2.set_source_surface(surf, 0, 0); c2.paint()
    out.write_to_png(str(OUT / 'watermark.png'))
    Image.open(OUT / 'watermark.png').resize((150, 150), Image.LANCZOS).save(OUT / 'watermark.png')


def main():
    OUT.mkdir(exist_ok=True)
    banner()
    head_shot('charlie', 800, 'excited').write_to_png(str(OUT / 'profile.png'))
    watermark()
    for p in sorted(OUT.glob('*.png')):
        print(p.name, Image.open(p).size, f'{p.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
