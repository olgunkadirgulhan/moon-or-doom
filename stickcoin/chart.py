"""Kendi mum grafiğimiz (Bölüm 9): 4 saatlik mumlar, animasyonlu destek/direnç çizgileri ve senaryo okları.

TradingView görüntüsü kullanılmaz (lisans). Renkler: yükselen #22C55E, düşen #EF4444.
"""
import math

import cairo

from . import words
from .rig import rrect

UP = (0x22 / 255, 0xC5 / 255, 0x5E / 255)
DOWN = (0xEF / 255, 0x44 / 255, 0x44 / 255)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def label(ctx, text, x, y, fg, bg, size=34, anchor='left', scale=1.0, alpha=1.0):
    """Kutulu fiyat etiketi; (x, y) = kutunun sol-orta noktası."""
    ctx.save()
    ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    ext = ctx.text_extents(text)
    w, h = ext.x_advance + 26, size * 1.35
    ctx.translate(x - (w if anchor == 'right' else 0) + w / 2, y)
    ctx.scale(scale, scale)
    ctx.translate(-w / 2, 0)
    rrect(ctx, 0, -h / 2, w, h, 10)
    ctx.set_source_rgba(*bg, alpha); ctx.fill()
    ctx.move_to(13 - ext.x_bearing, size * 0.36)
    ctx.set_source_rgba(*fg, alpha); ctx.show_text(text)
    ctx.restore()
    return w


class Chart:
    def __init__(self, data, rect):
        self.d = data
        self.x0, self.y0, self.w, self.h = rect
        self.c = data['chart']['candles']
        # çizim alanı: sağda etiketler için boşluk
        self.px0, self.px1 = self.x0 + 24, self.x0 + self.w - 230
        self.py0, self.py1 = self.y0 + 78, self.y0 + self.h - 56
        lows = [k[3] for k in self.c] + [v for v in (data['support_1'], data['support_2']) if v]
        highs = [k[2] for k in self.c] + [v for v in (data['resistance_1'], data['resistance_2']) if v]
        lo, hi = min(lows), max(highs)
        pad = (hi - lo) * 0.07
        self.lo, self.hi = lo - pad, hi + pad

    def y(self, p):
        return self.py1 - (p - self.lo) / (self.hi - self.lo) * (self.py1 - self.py0)

    def xi(self, i):
        n = len(self.c)
        return self.px0 + (i + 0.5) * (self.px1 - self.px0) / n

    def last(self):
        return self.xi(len(self.c) - 1), self.y(self.c[-1][4])

    def focus(self, act):
        """Charlie'nin çubuğunun hedefi."""
        if act == 'draw_resistance':
            return self.px1 - 60, self.y(self.d['resistance_1'])
        if act == 'draw_support':
            return self.px1 - 60, self.y(self.d['support_1'])
        if act == 'highlight_scenario_up' and self.d.get('resistance_2'):
            return self.px1 + 10, self.y(self.d['resistance_2'])
        if act == 'highlight_scenario_down' and self.d.get('support_2'):
            return self.px1 + 10, self.y(self.d['support_2'])
        return self.last()

    def panel(self, ctx):
        rrect(ctx, self.x0, self.y0, self.w, self.h, 28)
        ctx.set_source_rgba(0.06, 0.09, 0.18, 0.92); ctx.fill_preserve()
        ctx.set_source_rgba(1, 1, 1, 0.12); ctx.set_line_width(3); ctx.stroke()
        ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(28)
        ctx.set_source_rgba(1, 1, 1, 0.55)
        ctx.move_to(self.x0 + 28, self.y0 + 48)
        ctx.show_text(f"{self.d['coin']['symbol']}/USDT  ·  4H  ·  LAST 7 DAYS")
        ctx.set_font_size(22)
        ctx.set_source_rgba(1, 1, 1, 0.38)
        txt = 'EDUCATIONAL ONLY · NOT FINANCIAL ADVICE'
        ext = ctx.text_extents(txt)
        ctx.move_to(self.x0 + (self.w - ext.width) / 2, self.y0 + self.h - 20)
        ctx.show_text(txt)
        ctx.set_source_rgba(1, 1, 1, 0.05); ctx.set_line_width(2)
        for k in range(1, 5):
            yy = self.py0 + k * (self.py1 - self.py0) / 5
            ctx.move_to(self.px0, yy); ctx.line_to(self.px1, yy)
        ctx.stroke()

    def candles(self, ctx, p):
        n = len(self.c)
        cw = (self.px1 - self.px0) / n
        shown = p * n
        for i, (_, o, h, l, c) in enumerate(self.c):
            if i >= shown:
                break
            k = min(1.0, shown - i)
            col = UP if c >= o else DOWN
            x = self.xi(i)
            mid = (o + c) / 2
            yo = self.y(mid) + (self.y(o) - self.y(mid)) * k
            yc = self.y(mid) + (self.y(c) - self.y(mid)) * k
            ctx.set_source_rgb(*col)
            ctx.set_line_width(max(2, cw * 0.12))
            ctx.move_to(x, self.y(mid) + (self.y(h) - self.y(mid)) * k)
            ctx.line_to(x, self.y(mid) + (self.y(l) - self.y(mid)) * k)
            ctx.stroke()
            top, bot = min(yo, yc), max(yo, yc)
            ctx.rectangle(x - cw * 0.34, top, cw * 0.68, max(2.5, bot - top))
            ctx.fill()

    def price_line(self, ctx, alpha):
        if alpha <= 0:
            return
        x, y = self.last()
        ctx.save()
        ctx.set_dash([4, 8]); ctx.set_line_width(2)
        ctx.set_source_rgba(1, 1, 1, 0.45 * alpha)
        ctx.move_to(self.px0, y); ctx.line_to(self.px1 + 6, y); ctx.stroke()
        ctx.restore()
        label(ctx, words.price_text(self.d['price']), self.px1 + 12, y, (0.06, 0.09, 0.18), (1, 1, 1), 28,
              alpha=alpha)

    def level(self, ctx, price, p, color, tag, pulse=0.0, faint=False):
        if p <= 0 or price is None:
            return
        y = self.y(price)
        x1 = self.px0 + (self.px1 - self.px0) * ease(p)
        ctx.save()
        ctx.set_dash([22, 14] if not faint else [10, 12])
        ctx.set_line_width(7 if not faint else 4)
        ctx.set_source_rgba(*color, 0.95 if not faint else 0.7)
        ctx.move_to(self.px0, y); ctx.line_to(x1, y); ctx.stroke()
        ctx.restore()
        if p > 0.75:
            a = min(1, (p - 0.75) / 0.25)
            text = f'{tag} {words.price_text(price)}'
            label(ctx, text, self.px1 + 12, y, (1, 1, 1), color, 34 if len(text) <= 10 else max(22, 34 - 3 * (len(text) - 10)),
                  scale=(0.6 + 0.4 * ease(a)) * (1 + 0.08 * pulse))

    def arrow(self, ctx, target, p, color):
        if p <= 0 or target is None:
            return
        x0, y0 = self.last()
        x1, y1 = self.px1 - 20, self.y(target)
        k = ease(p)
        xe, ye = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
        cx, cy = x0 + (x1 - x0) * 0.2, y1
        ctx.save()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(*color); ctx.set_line_width(10)
        ctx.move_to(x0, y0)
        ctx.curve_to(x0 + (cx - x0) * k, y0 + (cy - y0) * k, xe, ye, xe, ye)
        ctx.stroke()
        ang = math.atan2(ye - (y0 + (cy - y0) * k), xe - (x0 + (cx - x0) * k) + 1e-6)
        ctx.translate(xe, ye); ctx.rotate(ang)
        ctx.move_to(14, 0); ctx.line_to(-22, -20); ctx.line_to(-22, 20); ctx.close_path()
        ctx.fill()
        ctx.restore()

    def draw(self, ctx, st, t):
        """st: {action: (başlangıç zamanı)} ve aktif aksiyon."""
        self.panel(ctx)

        def prog(act, dur):
            return 0.0 if act not in st['started'] else max(0.0, min(1.0, (t - st['started'][act]) / dur))

        show = prog('show', 1.0)
        self.candles(ctx, show)
        # fiyat etiketi, üstüne binen seviye etiketi çıkınca kaybolur
        py = self.y(self.d['price'])
        near = [prog(a, 0.8) for a, k in (('draw_resistance', 'resistance_1'), ('draw_support', 'support_1'))
                if abs(self.y(self.d[k]) - py) < 52]
        self.price_line(ctx, ease((show - 0.8) / 0.2) * (1 - max(near, default=0)))
        pulse = math.sin(t * 9) * 0.5 + 0.5
        active = st.get('active')
        d = self.d
        self.level(ctx, d['resistance_1'], prog('draw_resistance', 0.8), DOWN, 'R',
                   pulse if active == 'draw_resistance' else 0)
        self.level(ctx, d['support_1'], prog('draw_support', 0.8), UP, 'S', pulse if active == 'draw_support' else 0)
        up, down = prog('highlight_scenario_up', 0.9), prog('highlight_scenario_down', 0.9)
        self.level(ctx, d.get('resistance_2'), up, UP, '→', pulse if active == 'highlight_scenario_up' else 0, True)
        self.arrow(ctx, d.get('resistance_2'), up, UP)
        self.level(ctx, d.get('support_2'), down, DOWN, '→', pulse if active == 'highlight_scenario_down' else 0, True)
        self.arrow(ctx, d.get('support_2'), down, DOWN)
