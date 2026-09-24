"""Arka plan: koyu lacivert ekran + alt 1/3'te piyasa ruh haline göre sahne (Bölüm 12: roket üssü, yağmurlu sokak, casino, uzay)."""
import math
import random

import cairo

from .rig import rrect

NAVY = (0x0F / 255, 0x17 / 255, 0x2A / 255)
NAMES = ['rocket_base', 'space', 'rainy_street', 'casino']


def for_mood(change_pct, rnd):
    if change_pct >= 10:
        return rnd.choice(['space', 'rocket_base'])
    if change_pct >= 0:
        return rnd.choice(['rocket_base', 'casino', 'space'])
    if change_pct <= -8:
        return 'rainy_street'
    return rnd.choice(['rainy_street', 'casino'])


def _stars(ctx, W, y0, y1, n, rnd, alpha=0.8):
    for _ in range(n):
        x, y, r = rnd.uniform(0, W), rnd.uniform(y0, y1), rnd.uniform(1, 3.2)
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, rnd.uniform(0.3, alpha)); ctx.fill()


def render(name, W, H, ground, top, seed=0):
    """Statik arka plan yüzeyi. top = sahne şeridinin başladığı y (grafiğin altı)."""
    rnd = random.Random(seed)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, 0.09, 0.13, 0.25)
    g.add_color_stop_rgb(0.55, *NAVY)
    g.add_color_stop_rgb(1, 0.03, 0.05, 0.11)
    ctx.set_source(g); ctx.paint()
    _stars(ctx, W, 0, top, 60, rnd, 0.35)

    if name == 'space':
        _stars(ctx, W, top, ground, 90, rnd)
        ctx.arc(W * 0.83, top + 120, 90, 0, 2 * math.pi)
        ctx.set_source_rgb(0.95, 0.62, 0.25); ctx.fill()
        ctx.save(); ctx.translate(W * 0.83, top + 120); ctx.scale(1.9, 0.35)
        ctx.arc(0, 0, 90, 0, 2 * math.pi); ctx.restore()
        ctx.set_source_rgba(1, 0.85, 0.6, 0.8); ctx.set_line_width(7); ctx.stroke()
        ctx.arc(W * 0.12, top + 70, 34, 0, 2 * math.pi)
        ctx.set_source_rgb(0.85, 0.86, 0.9); ctx.fill()
        # ay yüzeyi zemini
        ctx.move_to(0, ground - 30)
        for x in range(0, W + 60, 60):
            ctx.line_to(x, ground - 30 + 12 * math.sin(x * 0.02))
        ctx.line_to(W, H); ctx.line_to(0, H); ctx.close_path()
        ctx.set_source_rgb(0.55, 0.57, 0.63); ctx.fill()
        for _ in range(9):
            x, y = rnd.uniform(0, W), rnd.uniform(ground, H - 30)
            ctx.save(); ctx.translate(x, y); ctx.scale(1, 0.35); ctx.arc(0, 0, rnd.uniform(20, 45), 0, 2 * math.pi)
            ctx.restore(); ctx.set_source_rgb(0.45, 0.47, 0.53); ctx.fill()
    elif name == 'rocket_base':
        ctx.rectangle(0, top, W, ground - top)
        g2 = cairo.LinearGradient(0, top, 0, ground)
        g2.add_color_stop_rgb(0, 0.12, 0.2, 0.4); g2.add_color_stop_rgb(1, 0.95, 0.55, 0.3)
        ctx.set_source(g2); ctx.fill()
        # fırlatma kulesi
        tx = W * 0.5
        ctx.set_source_rgb(0.25, 0.27, 0.33); ctx.set_line_width(7)
        for dx in (-40, 40):
            ctx.move_to(tx + dx, ground); ctx.line_to(tx + dx, top + 60)
        for y in range(int(top + 80), int(ground), 60):
            ctx.move_to(tx - 40, y); ctx.line_to(tx + 40, y + 50)
        ctx.stroke()
        # roket
        rx = tx + 110
        rrect(ctx, rx - 32, top + 90, 64, ground - top - 150, 30)
        ctx.set_source_rgb(0.96, 0.96, 0.98); ctx.fill_preserve()
        ctx.set_source_rgb(0.1, 0.1, 0.12); ctx.set_line_width(4); ctx.stroke()
        ctx.move_to(rx - 32, top + 150); ctx.curve_to(rx - 30, top + 40, rx + 30, top + 40, rx + 32, top + 150)
        ctx.set_source_rgb(0.9, 0.2, 0.25); ctx.fill()
        ctx.arc(rx, top + 200, 18, 0, 2 * math.pi)
        ctx.set_source_rgb(0.4, 0.75, 1); ctx.fill_preserve(); ctx.set_source_rgb(0.1, 0.1, 0.12); ctx.stroke()
        ctx.rectangle(0, ground - 10, W, H - ground + 10)
        ctx.set_source_rgb(0.3, 0.32, 0.38); ctx.fill()
        ctx.set_source_rgb(0.95, 0.8, 0.1)
        for x in range(0, W, 80):
            ctx.rectangle(x, ground + 30, 40, 12)
        ctx.fill()
    elif name == 'rainy_street':
        ctx.rectangle(0, top, W, ground - top)
        ctx.set_source_rgb(0.14, 0.17, 0.24); ctx.fill()
        x = 0
        while x < W:
            w, h = rnd.uniform(90, 170), rnd.uniform(180, 380)
            ctx.rectangle(x, ground - h, w, h)
            ctx.set_source_rgb(0.2, 0.23, 0.31); ctx.fill()
            for wx in range(int(x + 15), int(x + w - 20), 35):
                for wy in range(int(ground - h + 20), int(ground - 40), 45):
                    if rnd.random() < 0.35:
                        ctx.rectangle(wx, wy, 16, 22)
                        ctx.set_source_rgba(1, 0.85, 0.4, 0.5); ctx.fill()
            x += w + rnd.uniform(4, 20)
        for lx in (W * 0.08, W * 0.92):  # sokak lambası
            ctx.set_source_rgb(0.1, 0.1, 0.12); ctx.set_line_width(8)
            ctx.move_to(lx, ground); ctx.line_to(lx, ground - 330); ctx.stroke()
            ctx.arc(lx, ground - 340, 16, 0, 2 * math.pi)
            ctx.set_source_rgb(1, 0.9, 0.55); ctx.fill()
        ctx.rectangle(0, ground - 10, W, H - ground + 10)
        ctx.set_source_rgb(0.2, 0.21, 0.25); ctx.fill()
        for _ in range(6):  # su birikintisi
            x = rnd.uniform(0, W)
            ctx.save(); ctx.translate(x, rnd.uniform(ground + 30, H - 40)); ctx.scale(1, 0.18)
            ctx.arc(0, 0, rnd.uniform(40, 90), 0, 2 * math.pi); ctx.restore()
            ctx.set_source_rgba(0.5, 0.6, 0.8, 0.35); ctx.fill()
    else:  # casino
        ctx.rectangle(0, top, W, ground - top)
        ctx.set_source_rgb(0.28, 0.06, 0.12); ctx.fill()
        for i, sx in enumerate((W * 0.18, W * 0.5, W * 0.82)):  # slot makineleri
            rrect(ctx, sx - 95, ground - 330, 190, 330, 18)
            ctx.set_source_rgb(0.85, 0.65, 0.15); ctx.fill_preserve()
            ctx.set_source_rgb(0.1, 0.1, 0.12); ctx.set_line_width(4); ctx.stroke()
            for k in range(3):
                rrect(ctx, sx - 78 + k * 54, ground - 270, 46, 70, 6)
                ctx.set_source_rgb(1, 1, 1); ctx.fill()
                ctx.arc(sx - 55 + k * 54, ground - 235, 13, 0, 2 * math.pi)
                ctx.set_source_rgb(*[(0.9, 0.15, 0.2), (0.2, 0.75, 0.3), (0.95, 0.75, 0.1)][(k + i) % 3]); ctx.fill()
        for x in range(20, W, 45):  # ampul sırası
            ctx.arc(x, top + 30, 8, 0, 2 * math.pi)
            ctx.set_source_rgb(1, 0.85, 0.3); ctx.fill()
        ctx.rectangle(0, ground - 10, W, H - ground + 10)
        ctx.set_source_rgb(0.55, 0.08, 0.12); ctx.fill()
    # sahne üst kenarını grafikten ayıran yumuşak geçiş
    g3 = cairo.LinearGradient(0, top - 10, 0, top + 110)
    g3.add_color_stop_rgba(0, *NAVY, 1)
    g3.add_color_stop_rgba(1, *NAVY, 0)
    ctx.rectangle(0, top - 10, W, 120); ctx.set_source(g3); ctx.fill()
    surf.flush()
    return surf


def dynamic(ctx, name, W, ground, top, t):
    """Kareye özel hareket: yağmur, yanıp sönen ampuller, parlayan yıldızlar."""
    if name == 'rainy_street':
        ctx.set_source_rgba(0.7, 0.8, 1, 0.45); ctx.set_line_width(2.5)
        r = random.Random(7)
        for _ in range(90):
            x0, sp = r.uniform(0, W + 200), r.uniform(900, 1400)
            y = top + ((r.uniform(0, 1000) + t * sp) % (ground - top + 200)) - 100
            x = x0 - (y - top) * 0.25
            ctx.move_to(x, y); ctx.line_to(x - 9, y + 36)
        ctx.stroke()
    elif name == 'casino':
        for i, x in enumerate(range(20, W, 45)):
            if (i + int(t * 6)) % 3 == 0:
                ctx.arc(x, top + 30, 12, 0, 2 * math.pi)
                ctx.set_source_rgba(1, 1, 0.8, 0.9); ctx.fill()
    elif name == 'rocket_base':
        k = 0.5 + 0.5 * math.sin(t * 3)
        ctx.arc(W * 0.5, top + 60, 10, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 0.2, 0.2, 0.4 + 0.6 * k); ctx.fill()
