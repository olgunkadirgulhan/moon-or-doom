"""Bilgi panoları (scene "board"). İçerik tamamen koddan: sayılar veri JSON'undan, metinler sabit.

stats         günün kartı: 24s / 7g değişim, hacim, RSI, piyasa değeri sırası
about         "WHAT IS X?": logo, kategori çipleri, çıkış yılı
title         uzun video segment başlığı: etiket + logo + haftalık değişim
lesson_rsi    RSI göstergesi (ibre coinin RSI'sına döner)
lesson_sr     destek/direnç arasında seken fiyat illüstrasyonu
lesson_volume son 7 günün hacim çubukları + ortalama çizgisi
lesson_trend  fiyat + hızlı/yavaş ortalama
lesson_candle mum anatomisi
"""
import math

import cairo
import numpy as np

from . import words
from .chart import DOWN, UP, ease, label
from .rig import rrect

WHITE = (1, 1, 1)
MUTED = (0.65, 0.72, 0.85)
GOLD = (1.0, 0.84, 0.16)


def panel(ctx, rect, alpha=1.0):
    x, y, w, h = rect
    rrect(ctx, x, y, w, h, 28)
    ctx.set_source_rgba(0.06, 0.09, 0.18, 0.94 * alpha); ctx.fill_preserve()
    ctx.set_source_rgba(1, 1, 1, 0.12 * alpha); ctx.set_line_width(3); ctx.stroke()


def text(ctx, s, x, y, size, color=WHITE, anchor='left', bold=True, alpha=1.0):
    ctx.save()
    ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    dx = {'left': 0, 'center': -ext.x_advance / 2, 'right': -ext.x_advance}[anchor]
    ctx.move_to(x + dx, y)
    ctx.set_source_rgba(*color, alpha); ctx.show_text(s)
    ctx.restore()
    return ext.x_advance


def fit(ctx, s, size, maxw):
    ctx.save()
    ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    while size > 16:
        ctx.set_font_size(size)
        if ctx.text_extents(s).x_advance <= maxw:
            break
        size -= 2
    ctx.restore()
    return size


def paste(ctx, surf, cx, cy, scale=1.0, alpha=1.0):
    ctx.save(); ctx.translate(cx, cy); ctx.scale(scale, scale)
    ctx.set_source_surface(surf, -surf.get_width() / 2, -surf.get_height() / 2)
    ctx.paint_with_alpha(alpha); ctx.restore()


def title_bar(ctx, rect, s, k, color=GOLD):
    x, y, w, h = rect
    size = fit(ctx, s, int(h * 0.075), w - 80)
    text(ctx, s, x + w / 2, y + h * 0.13, size, color, 'center', alpha=ease(k / 0.3))


def pct_color(v):
    return UP if v >= 0 else DOWN


# ------------------------------------------------------------------ panolar

def stats(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, f"{d['coin']['symbol']} · TODAY'S CARD", k)
    rows = [('24H CHANGE', f"{'+' if d['change_24h_pct'] >= 0 else '-'}{words.pct_text(d['change_24h_pct'])}",
             pct_color(d['change_24h_pct']))]
    if d.get('change_7d_pct') is not None:
        rows.append(('7D CHANGE', f"{'+' if d['change_7d_pct'] >= 0 else '-'}{words.pct_text(d['change_7d_pct'])}",
                     pct_color(d['change_7d_pct'])))
    rows.append(('PRICE', words.price_text(d['price']), WHITE))
    if d.get('volume_vs_avg') is not None:
        rows.append(('VOLUME VS AVG', f"{d['volume_vs_avg']:.1f}x", GOLD if d['volume_vs_avg'] >= 1.5 else WHITE))
    if d.get('rsi_14') is not None:
        r = d['rsi_14']
        rows.append(('RSI (14, 4H)', f'{r:.0f}', DOWN if r >= 70 else UP if r <= 30 else WHITE))
    if d['coin'].get('market_cap_rank'):
        rows.append(('MARKET CAP RANK', f"#{d['coin']['market_cap_rank']}", WHITE))
    top, gap = y + h * 0.22, (h * 0.72) / max(len(rows), 1)
    size = int(min(gap * 0.42, h * 0.055))
    for i, (lab, val, col) in enumerate(rows):
        a = ease((k - 0.15 - i * 0.12) / 0.25)
        if a <= 0:
            continue
        yy = top + i * gap + gap * 0.6
        text(ctx, lab, x + 50 - 30 * (1 - a), yy, int(size * 0.8), MUTED, alpha=a)
        text(ctx, val, x + w - 50, yy, int(size * 1.25), col, 'right', alpha=a)
        if i:
            ctx.set_source_rgba(1, 1, 1, 0.06); ctx.set_line_width(2)
            ctx.move_to(x + 40, yy - gap * 0.62); ctx.line_to(x + w - 40, yy - gap * 0.62); ctx.stroke()


def about(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, f"WHAT IS {d['coin']['name'].upper()}?", k)
    paste(ctx, logo, x + w / 2, y + h * 0.40, (0.6 + 0.4 * ease(k / 0.35)) * min(1.0, h / 900), ease(k / 0.3))
    info = d.get('info') or {}
    chips = [c.upper() for c in (info.get('categories') or [])][:4]
    cy = y + h * 0.66
    ctx.save()
    ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    size = int(h * 0.036)
    ctx.set_font_size(size)
    widths = [min(ctx.text_extents(c).x_advance, w - 140) + 44 for c in chips]
    ctx.restore()
    rows, cur = [], []
    for c, cw in zip(chips, widths):
        if cur and sum(v for _, v in cur) + cw + 16 * len(cur) > w - 80:
            rows.append(cur); cur = []
        cur.append((c, cw))
    if cur:
        rows.append(cur)
    n = 0
    for r, row in enumerate(rows):
        total = sum(cw for _, cw in row) + 16 * (len(row) - 1)
        xx = x + (w - total) / 2
        for c, cw in row:
            a = ease((k - 0.3 - n * 0.12) / 0.25); n += 1
            if a > 0:
                rrect(ctx, xx, cy + r * size * 1.9 - size, cw, size * 1.6, size * 0.8)
                ctx.set_source_rgba(0.25, 0.45, 0.95, 0.9 * a); ctx.fill()
                s2 = fit(ctx, c, size, cw - 44)
                text(ctx, c, xx + cw / 2, cy + r * size * 1.9 + size * 0.1, s2, WHITE, 'center', alpha=a)
            xx += cw + 16
    facts = []
    if info.get('launched'):
        facts.append(f"LAUNCHED {info['launched']}")
    if d['coin'].get('market_cap_rank'):
        facts.append(f"MARKET CAP #{d['coin']['market_cap_rank']}")
    if facts:
        text(ctx, '  ·  '.join(facts), x + w / 2, y + h * 0.9, int(h * 0.04), MUTED, 'center', alpha=ease((k - 0.6) / 0.3))


def title_card(ctx, rect, d, k, logo, label_text=''):
    x, y, w, h = rect
    text(ctx, label_text.upper(), x + w / 2, y + h * 0.18, fit(ctx, label_text.upper(), int(h * 0.07), w - 80), GOLD,
         'center', alpha=ease(k / 0.3))
    paste(ctx, logo, x + w / 2, y + h * 0.45, (0.5 + 0.5 * ease(k / 0.4)) * min(1.0, h / 900))
    text(ctx, d['coin']['symbol'], x + w / 2, y + h * 0.75, int(h * 0.1), WHITE, 'center', alpha=ease((k - 0.2) / 0.3))
    chg = d.get('change_7d_pct')
    if chg is None:
        chg, tag = d['change_24h_pct'], '24H'
    else:
        tag = '7D'
    s = f"{'+' if chg >= 0 else '-'}{abs(chg * ease((k - 0.3) / 0.8)):.1f}% {tag}"
    text(ctx, s, x + w / 2, y + h * 0.88, int(h * 0.07), pct_color(chg), 'center', alpha=ease((k - 0.3) / 0.3))


def lesson_rsi(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, 'RSI (14) · MOMENTUM GAUGE', k)
    cx, cy, R = x + w / 2, y + h * 0.72, min(w * 0.38, h * 0.48)
    ctx.save()
    ctx.set_line_width(R * 0.22)
    for a0, a1, col in ((0, 0.3, UP), (0.3, 0.7, (0.55, 0.6, 0.7)), (0.7, 1.0, DOWN)):
        ctx.new_path()
        ctx.arc(cx, cy, R, math.pi + a0 * math.pi, math.pi + a1 * math.pi)
        ctx.set_source_rgb(*col); ctx.stroke()
    ctx.restore()
    for v, lab in ((0.15, 'OVERSOLD'), (0.5, 'NEUTRAL'), (0.85, 'OVERBOUGHT')):
        ang = math.pi + v * math.pi
        text(ctx, lab, cx + math.cos(ang) * R * 1.32, cy + math.sin(ang) * R * 1.32, int(h * 0.032), WHITE, 'center')
    rsi = d.get('rsi_14') or 50
    val = 50 + (rsi - 50) * ease((k - 0.2) / 0.9)
    ang = math.pi + val / 100 * math.pi
    ctx.set_source_rgb(*WHITE); ctx.set_line_width(10); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(cx, cy); ctx.line_to(cx + math.cos(ang) * R * 0.92, cy + math.sin(ang) * R * 0.92); ctx.stroke()
    ctx.arc(cx, cy, 18, 0, 2 * math.pi); ctx.fill()
    text(ctx, f"{d['coin']['symbol']} RSI {val:.0f}", cx, cy + h * 0.13, int(h * 0.065), GOLD, 'center',
         alpha=ease((k - 0.3) / 0.3))


def lesson_sr(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, 'SUPPORT & RESISTANCE', k)
    top, bot = y + h * 0.32, y + h * 0.78
    for yy, col, lab in ((top, DOWN, 'RESISTANCE · SELLERS SHOWED UP'), (bot, UP, 'SUPPORT · BUYERS SHOWED UP')):
        ctx.save(); ctx.set_dash([22, 14]); ctx.set_line_width(7); ctx.set_source_rgb(*col)
        ctx.move_to(x + 40, yy); ctx.line_to(x + 40 + (w - 80) * ease(k / 0.6), yy); ctx.stroke(); ctx.restore()
        text(ctx, lab, x + w / 2, yy + (-18 if col == DOWN else 46), int(h * 0.035), col, 'center', alpha=ease((k - 0.4) / 0.3))
    pts = [(0.0, 0.5), (0.12, 0.95), (0.25, 0.1), (0.38, 0.9), (0.5, 0.05), (0.63, 0.92), (0.76, 0.12), (0.9, 0.85), (1.0, 0.4)]
    prog = ease((k - 0.3) / 1.8)
    ctx.set_source_rgb(*WHITE); ctx.set_line_width(6); ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    last = None
    for i, (px, py) in enumerate(pts):
        if px > prog:
            if last:
                (lx, ly) = last
                f = (prog - lx) / max(1e-6, px - lx)
                ctx.line_to(x + 60 + (lx + (px - lx) * f) * (w - 120), top + 20 + (ly + (py - ly) * f) * (bot - top - 40))
            break
        X, Y = x + 60 + px * (w - 120), top + 20 + py * (bot - top - 40)
        (ctx.move_to if i == 0 else ctx.line_to)(X, Y)
        last = (px, py)
    ctx.stroke()


def lesson_volume(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, f"{d['coin']['symbol']} VOLUME · LAST 7 DAYS", k)
    c = d['chart']['candles']
    vols = np.array([row[5] if len(row) > 5 else 0 for row in c], dtype=float)
    if vols.max() <= 0:
        return
    avg = vols.mean()
    px0, px1, py0, py1 = x + 40, x + w - 40, y + h * 0.25, y + h * 0.88
    bw = (px1 - px0) / len(vols)
    shown = ease(k / 1.2) * len(vols)
    for i, v in enumerate(vols):
        if i > shown:
            break
        bh = (py1 - py0) * v / vols.max()
        col = UP if c[i][4] >= c[i][1] else DOWN
        ctx.rectangle(px0 + i * bw + bw * 0.15, py1 - bh, bw * 0.7, bh)
        ctx.set_source_rgb(*col); ctx.fill()
    if k > 1.0:
        ay = py1 - (py1 - py0) * avg / vols.max()
        ctx.save(); ctx.set_dash([14, 10]); ctx.set_line_width(5); ctx.set_source_rgb(*GOLD)
        ctx.move_to(px0, ay); ctx.line_to(px1, ay); ctx.stroke(); ctx.restore()
        text(ctx, 'AVERAGE', px1 - 10, ay - 14, int(h * 0.035), GOLD, 'right')


def lesson_trend(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, 'MOVING AVERAGES · TREND', k)
    closes = np.array([row[4] for row in d['chart']['candles']], dtype=float)

    def ema(v, span):
        a, out = 2 / (span + 1), [v[0]]
        for z in v[1:]:
            out.append(z * a + out[-1] * (1 - a))
        return np.array(out)
    series = [(closes, WHITE, 'PRICE', 6), (ema(closes, 8), GOLD, 'FAST AVG', 5), (ema(closes, 21), (0.4, 0.7, 1.0), 'SLOW AVG', 5)]
    lo, hi = min(s.min() for s, *_ in series), max(s.max() for s, *_ in series)
    px0, px1, py0, py1 = x + 40, x + w - 40, y + h * 0.24, y + h * 0.84
    n = len(closes)
    upto = max(2, int(ease(k / 1.4) * n))
    for s, col, lab, lw in series:
        ctx.set_source_rgb(*col); ctx.set_line_width(lw)
        for i in range(upto):
            X = px0 + i / (n - 1) * (px1 - px0)
            Y = py1 - (s[i] - lo) / max(hi - lo, 1e-12) * (py1 - py0)
            (ctx.move_to if i == 0 else ctx.line_to)(X, Y)
        ctx.stroke()
    for i, (s, col, lab, lw) in enumerate(series):
        text(ctx, lab, x + 50 + i * (w - 100) / 3, y + h * 0.94, int(h * 0.035), col, alpha=ease((k - 0.5) / 0.3))


def lesson_candle(ctx, rect, d, k, logo):
    x, y, w, h = rect
    title_bar(ctx, rect, 'ANATOMY OF A CANDLE', k)
    for j, (col, up) in enumerate(((UP, True), (DOWN, False))):
        a = ease((k - j * 0.5) / 0.4)
        if a <= 0:
            continue
        cx = x + w * (0.3 + 0.4 * j)
        top, bot = y + h * 0.28, y + h * 0.86
        b0, b1 = y + h * 0.42, y + h * 0.7
        ctx.set_source_rgba(*col, a); ctx.set_line_width(8)
        ctx.move_to(cx, top); ctx.line_to(cx, bot); ctx.stroke()
        ctx.rectangle(cx - w * 0.07, b0, w * 0.14, b1 - b0); ctx.fill()
        sz = int(h * 0.032)
        text(ctx, 'HIGH', cx + w * 0.02, top + 8, sz, MUTED, alpha=a)
        text(ctx, 'LOW', cx + w * 0.02, bot, sz, MUTED, alpha=a)
        text(ctx, 'CLOSE' if up else 'OPEN', cx + w * 0.09, b0 + sz * 0.4, sz, WHITE, alpha=a)
        text(ctx, 'OPEN' if up else 'CLOSE', cx + w * 0.09, b1 + sz * 0.4, sz, WHITE, alpha=a)
        text(ctx, 'CLOSED HIGHER' if up else 'CLOSED LOWER', cx, y + h * 0.95, sz, col, 'center', alpha=a)


BOARDS = {'stats': stats, 'about': about, 'title': title_card, 'lesson_rsi': lesson_rsi, 'lesson_sr': lesson_sr,
          'lesson_volume': lesson_volume, 'lesson_trend': lesson_trend, 'lesson_candle': lesson_candle}


def draw(ctx, kind, rect, data, k, logo, label_text=''):
    """k: panonun görünmeye başlamasından beri geçen saniye."""
    x, y, w, h = rect
    ctx.save()
    s = 0.92 + 0.08 * ease(k / 0.25)
    ctx.translate(x + w / 2, y + h / 2); ctx.scale(s, s); ctx.translate(-(x + w / 2), -(y + h / 2))
    panel(ctx, rect, ease(k / 0.2))
    if kind == 'title':
        title_card(ctx, rect, data, k, logo, label_text)
    else:
        BOARDS.get(kind, stats)(ctx, rect, data, k, logo)
    ctx.restore()
