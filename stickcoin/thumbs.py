"""Uzun video küçük resmi (1280x720): yeşil/kırmızı zemin, büyük başlık, coin logoları, Max ve Betty."""
import math
import random

import cairo

from . import rig
from .chart import DOWN, UP
from .render import logo_surface, pil_to_surface, text_block


def _bg(ctx, W, H):
    g = cairo.LinearGradient(0, 0, W, 0)
    g.add_color_stop_rgb(0, 0.04, 0.4, 0.2)
    g.add_color_stop_rgb(0.5, 0.06, 0.09, 0.17)
    g.add_color_stop_rgb(1, 0.55, 0.05, 0.09)
    ctx.set_source(g); ctx.paint()
    rnd = random.Random(1)
    for _ in range(140):
        ctx.arc(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1, 3), 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, rnd.uniform(0.2, 0.6)); ctx.fill()


def _char(ctx, cid, x, ground, s, facing, emotion, pose, mouth):
    st = dict(rig.pose_targets(pose))
    st.update(emotion=emotion, mouth=mouth, t=0.2, breath=1.0, bend=st.get('bend', 'out'))
    rig.draw(ctx, cid, x, ground, s, facing, st)


def make(path, title_words, sub_words, datas):
    W, H = 1280, 720
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    _bg(ctx, W, H)
    _char(ctx, 'moon_max', 150, 700, 4.6, 1, 'excited', 'celebrate', 'wide')
    _char(ctx, 'bear_betty', W - 150, 700, 4.6, -1, 'shock', 'crying', 'wide')
    t = pil_to_surface(text_block(title_words, 96, 860, color=(255, 222, 40), stroke_w=9))
    ctx.set_source_surface(t, (W - t.get_width()) / 2, 40); ctx.paint()
    s = pil_to_surface(text_block(sub_words, 46, 860, stroke_w=5))
    ctx.set_source_surface(s, (W - s.get_width()) / 2, 70 + t.get_height()); ctx.paint()
    n = min(len(datas), 6)
    for i, d in enumerate(datas[:n]):
        lg = logo_surface(d, 104)
        x = W / 2 + (i - (n - 1) / 2) * 138
        y = 560
        ctx.set_source_surface(lg, x - lg.get_width() / 2, y - lg.get_height() / 2); ctx.paint()
        chg = d.get('change_7d_pct')
        chg = d['change_24h_pct'] if chg is None else chg
        tag = pil_to_surface(text_block([f"{'+' if chg >= 0 else '-'}{abs(chg):.0f}%"], 38, 200,
                                        color=tuple(int(v * 255) for v in (UP if chg >= 0 else DOWN)), stroke_w=4))
        ctx.set_source_surface(tag, x - tag.get_width() / 2, y + 60); ctx.paint()
    surf.write_to_png(str(path))
    return path
