"""Vektör çöp adam rig'i (cairo) — çizgiKarakter/stickstory rig'inden, kripto kadrosu için.

Karakter yerel koordinatlarda çizilir: orijin = ayak ortası (zemin), y aşağı, boy ~100 birim.
Yüz 'sağa bakan' çerçevede tanımlıdır; sola bakan karakter x ekseninde aynalanır.
Kollar/bacaklar 2 kemikli IK ile hesaplanır ama tek eğri çizgi olarak çizilir (eklem görünmez).
"""
import math

import cairo

from .cast import CAST

INK = (0.07, 0.07, 0.09)
LW = 1.05          # kontur kalınlığı (birim)
LIMB = 1.35        # kol/bacak kalınlığı
ARM = (13.0, 13.5)
LEG = (16.0, 16.5)
SHOULDER = (9.0, -55.0)
HIP = (4.5, -32.0)
HEAD = (0.0, -77.0)
HEAD_R = 19.0

# el/ayak hedefleri (sağa bakan çerçeve). f = öndeki (bakılan taraftaki) uzuv, b = arkadaki
P = {
    'standing':     dict(hf=(14, -31), hb=(-14, -31)),
    'arms_crossed': dict(hf=(-5, -44), hb=(5, -42.5), cross=True),
    'hips':         dict(hf=(10.5, -34), hb=(-10.5, -34)),
    'pointing':     dict(hf=(35, -61), hb=(-14, -31)),
    'shrug':        dict(hf=(24, -63), hb=(-24, -63), bend='down'),
    'celebrate':    dict(hf=(24, -96), hb=(-24, -96)),
    'facepalm':     dict(hf=(6, -78), hb=(-14, -31), front=True),
    'thinking':     dict(hf=(6, -63), hb=(-13, -32), front=True),
    'crying':       dict(hf=(11, -63), hb=(-11, -63), bend='down'),
}
DEFAULT_FEET = dict(ff=(8, 0), fb=(-8, 0), drop=0)


def pose_targets(name):
    p = dict(DEFAULT_FEET)
    p.update(P.get(name, P['standing']))
    return p


def ik(root, target, l1, l2, prefer):
    """2 kemikli IK. prefer(elbow_a, elbow_b) -> seçilen dirsek."""
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = max(1e-3, math.hypot(dx, dy))
    d_c = min(d, l1 + l2 - 0.01)
    a = math.acos(max(-1, min(1, (l1 * l1 + d_c * d_c - l2 * l2) / (2 * l1 * d_c))))
    base = math.atan2(dy, dx)
    cands = [(root[0] + l1 * math.cos(base + s * a), root[1] + l1 * math.sin(base + s * a)) for s in (1, -1)]
    elbow = prefer(*cands)
    ux, uy = dx / d, dy / d
    end = (root[0] + ux * d_c, root[1] + uy * d_c) if d > d_c else target
    ex, ey = end[0] - elbow[0], end[1] - elbow[1]
    el = max(1e-3, math.hypot(ex, ey))
    hand = (elbow[0] + ex / el * l2, elbow[1] + ey / el * l2)
    return elbow, hand


def limb_path(ctx, a, b, c):
    """Omuz->dirsek->el tek yumuşak eğri (kontrol noktası dirseğin biraz ötesinde)."""
    cx, cy = 2 * b[0] - (a[0] + c[0]) / 2, 2 * b[1] - (a[1] + c[1]) / 2
    ctx.move_to(*a)
    ctx.curve_to(a[0] + (cx - a[0]) * 0.66, a[1] + (cy - a[1]) * 0.66,
                 c[0] + (cx - c[0]) * 0.66, c[1] + (cy - c[1]) * 0.66, *c)


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def fill_stroke(ctx, fill, lw=LW, stroke=INK):
    ctx.set_source_rgb(*fill)
    ctx.fill_preserve()
    ctx.set_source_rgb(*stroke)
    ctx.set_line_width(lw)
    ctx.stroke()


def poly(ctx, pts):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()


def darker(c, k=0.75):
    return tuple(max(0, v * k) for v in c)


# ---------------------------------------------------------------- gövde / kostüm

def rocket_badge(ctx, x, y, s=1.0):
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
    ctx.arc(0, 0, 4.6, 0, 2 * math.pi)
    fill_stroke(ctx, (1, 1, 1), 0.6)
    ctx.rotate(0.6)
    poly(ctx, [(0, -3.6), (1.3, -1.2), (1.3, 2), (-1.3, 2), (-1.3, -1.2)])
    fill_stroke(ctx, (0.85, 0.2, 0.25), 0.4)
    poly(ctx, [(-1.3, 0.6), (-2.6, 2.6), (-1.3, 2)])
    poly(ctx, [(1.3, 0.6), (2.6, 2.6), (1.3, 2)])
    ctx.set_source_rgb(0.3, 0.3, 0.35); ctx.fill()
    poly(ctx, [(-0.9, 2.1), (0, 3.9), (0.9, 2.1)])
    ctx.set_source_rgb(1, 0.65, 0.1); ctx.fill()
    ctx.restore()


def torso(ctx, cid, c):
    shirt = c['shirt']
    if cid == 'moon_max':  # hoodie + kanguru cep + ipler + roket rozeti
        poly(ctx, [(-10.5, -57.5), (10.5, -57.5), (11, -29), (-11, -29)])
        fill_stroke(ctx, shirt)
        rrect(ctx, -6.5, -40, 13, 7, 2)
        fill_stroke(ctx, darker(shirt, 0.88), 0.6)
        ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(0.6)
        ctx.move_to(-2, -57); ctx.line_to(-2.5, -49); ctx.move_to(2, -57); ctx.line_to(2.5, -49); ctx.stroke()
        rocket_badge(ctx, 5.5, -50.5, 0.8)
    elif cid == 'bear_betty':  # kırmızı ceket, yakalar, siyah iç
        poly(ctx, [(-10, -57.5), (10, -57.5), (11.5, -28), (-11.5, -28)])
        fill_stroke(ctx, shirt)
        poly(ctx, [(-3.5, -57.5), (3.5, -57.5), (0, -44)])
        fill_stroke(ctx, (0.12, 0.12, 0.14), 0.6)
        ctx.set_source_rgb(*darker(shirt, 0.65)); ctx.set_line_width(0.8)
        ctx.move_to(-3.5, -57.5); ctx.line_to(-6.5, -47); ctx.line_to(-1.5, -41)
        ctx.move_to(3.5, -57.5); ctx.line_to(6.5, -47); ctx.line_to(1.5, -41)
        ctx.stroke()
        for y in (-37, -32.5):
            ctx.arc(1.5, y, 0.9, 0, 2 * math.pi)
            ctx.set_source_rgb(0.1, 0.1, 0.1); ctx.fill()
    else:  # charlie: mavi gömlek, yaka, lacivert kravat, cep kalemi
        poly(ctx, [(-10, -57.5), (10, -57.5), (9.5, -30), (-9.5, -30)])
        fill_stroke(ctx, shirt)
        poly(ctx, [(-5, -58), (0, -54), (-4, -52)])
        fill_stroke(ctx, (0.9, 0.94, 1.0), 0.5)
        poly(ctx, [(5, -58), (0, -54), (4, -52)])
        fill_stroke(ctx, (0.9, 0.94, 1.0), 0.5)
        poly(ctx, [(0, -54.5), (1.6, -51), (1.1, -40), (0, -37.5), (-1.1, -40), (-1.6, -51)])
        fill_stroke(ctx, (0.1, 0.16, 0.35), 0.5)
        rrect(ctx, -8, -50, 4.5, 4.5, 0.8)
        fill_stroke(ctx, darker(shirt, 0.85), 0.5)
        ctx.set_source_rgb(0.95, 0.8, 0.15); ctx.set_line_width(0.8)
        ctx.move_to(-6.5, -50); ctx.line_to(-6.5, -53); ctx.stroke()


def behind_head(ctx, cid, c):
    if cid == 'moon_max':  # kapüşon
        ctx.save(); ctx.translate(-3, -62); ctx.scale(1.0, 0.55)
        ctx.arc(0, 0, 15, 0, 2 * math.pi); ctx.restore()
        fill_stroke(ctx, darker(c['shirt'], 0.9))
    if cid == 'bear_betty':  # küt saç arka kısmı
        rrect(ctx, -HEAD_R - 2, HEAD[1] - 8, 2 * HEAD_R + 1, 22, 5)
        fill_stroke(ctx, (0.16, 0.1, 0.08))


def hair_and_hats(ctx, cid, c):
    hx, hy = HEAD
    if cid == 'moon_max':  # dağınık diken saç
        ctx.new_path()
        ctx.move_to(hx - HEAD_R, hy - 2)
        spikes = [(-17, -24), (-11, -16), (-7, -29), (-1, -18), (4, -30), (8, -18), (15, -26), (13, -13), (HEAD_R, -4)]
        for dx, dy in spikes:
            ctx.line_to(hx + dx, hy + dy)
        ctx.arc_negative(hx, hy - 3, HEAD_R - 4, -0.1, math.pi + 0.1)
        ctx.close_path()
        fill_stroke(ctx, (0.45, 0.27, 0.12), 0.8)
    elif cid == 'bear_betty':  # küt kesim + düz kakül
        ctx.new_path(); ctx.arc(hx, hy, HEAD_R + 1, math.pi * 0.98, math.pi * 2.02)
        ctx.line_to(hx + HEAD_R - 3, hy - 9)
        ctx.line_to(hx - 6, hy - 11)
        ctx.line_to(hx - HEAD_R + 1, hy + 4)
        ctx.close_path()
        fill_stroke(ctx, (0.16, 0.1, 0.08))
    else:  # charlie: yanlar gri, tepe seyrek
        ctx.new_path(); ctx.arc(hx, hy, HEAD_R + 0.8, math.pi * 1.0, math.pi * 1.62)
        ctx.curve_to(hx + 2, hy - 13, hx - 10, hy - 11, hx - HEAD_R + 2, hy + 2)
        ctx.close_path()
        fill_stroke(ctx, (0.62, 0.62, 0.66))
        ctx.new_path(); ctx.arc(hx, hy, HEAD_R + 0.8, math.pi * 1.85, math.pi * 2.0)
        ctx.line_to(hx + HEAD_R - 3, hy - 7); ctx.close_path()
        fill_stroke(ctx, (0.62, 0.62, 0.66), 0.7)


# ---------------------------------------------------------------- yüz

def face(ctx, cid, c, st):
    emo = st['emotion']
    t = st['t']
    ey = HEAD[1] - 2
    eyes = [(-3.0, ey), (9.5, ey)]
    er = 5.8
    look = st.get('look', (1.2, 0))
    pr = 2.6
    if emo == 'shock':
        er, pr = 7.2, 1.3
    elif emo in ('nervous', 'angry'):
        pr = 1.9
    elif emo == 'excited':
        er, pr = 6.6, 3.2
    if emo == 'nervous':
        look = (look[0] + 0.6 * math.sin(t * 40), look[1])
    if emo == 'sad':
        look = (look[0] * 0.5, 1.8)

    closed = st.get('blink', 0) > 0.5 or emo in ('happy', 'cry')
    for (x, y) in eyes:
        if closed:
            ctx.new_path()
            if emo == 'happy':
                ctx.arc(x, y + 1.5, 3.8, math.pi * 1.1, math.pi * 1.9)
            elif emo == 'cry':
                ctx.arc(x, y - 1.5, 3.8, math.pi * 0.15, math.pi * 0.85)
            else:
                ctx.move_to(x - 4.5, y); ctx.line_to(x + 4.5, y)
            ctx.set_source_rgb(*INK); ctx.set_line_width(1.2); ctx.stroke()
            continue
        ctx.arc(x, y, er, 0, 2 * math.pi)
        fill_stroke(ctx, (1, 1, 1), 0.9)
        if emo == 'shock':
            ctx.set_source_rgb(0.9, 0.15, 0.15); ctx.set_line_width(0.35)
            for k in range(5):
                a = k * 1.3 + 0.4
                ctx.move_to(x + er * 0.95 * math.cos(a), y + er * 0.95 * math.sin(a))
                ctx.line_to(x + er * 0.5 * math.cos(a + 0.3), y + er * 0.5 * math.sin(a + 0.3))
            ctx.stroke()
        px, py = x + look[0], y + look[1]
        ctx.arc(px, py, pr, 0, 2 * math.pi)
        ctx.set_source_rgb(*INK); ctx.fill()
        ctx.arc(px + pr * 0.35, py - pr * 0.4, pr * 0.32, 0, 2 * math.pi)
        ctx.set_source_rgb(1, 1, 1); ctx.fill()
        if emo == 'excited':
            ctx.arc(px - 1, py + 1, 0.8, 0, 2 * math.pi); ctx.fill()
        if emo in ('smug', 'suspicious'):  # yarı kapalı göz kapağı
            ctx.save(); ctx.arc(x, y, er - 0.3, 0, 2 * math.pi); ctx.clip()
            ctx.rectangle(x - er, y - er, 2 * er, er * (1.05 if emo == 'suspicious' else 0.8))
            ctx.set_source_rgb(*c['skin']); ctx.fill(); ctx.restore()
            ctx.set_source_rgb(*INK); ctx.set_line_width(0.9)
            yy = y - er + er * (1.05 if emo == 'suspicious' else 0.8)
            ctx.move_to(x - er, yy); ctx.line_to(x + er, yy); ctx.stroke()
    if cid == 'charlie':  # dikdörtgen gözlük
        for (x, y) in eyes:
            rrect(ctx, x - 7.2, y - 5.8, 14.4, 11.6, 2.5)
            ctx.set_source_rgba(0.85, 0.95, 1, 0.18); ctx.fill_preserve()
            ctx.set_source_rgb(*INK); ctx.set_line_width(1.4); ctx.stroke()
        ctx.move_to(eyes[0][0] + 7.2, ey - 1); ctx.line_to(eyes[1][0] - 7.2, ey - 1); ctx.stroke()

    # kaşlar (Betty: kalın)
    by = ey - (er + 3.2)
    thick = cid == 'bear_betty'
    ctx.set_source_rgb(*INK); ctx.set_line_width((2.8 if thick else 1.1) + (0.4 if emo == 'angry' else 0))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    (x0, x1) = eyes[0][0], eyes[1][0]
    if emo == 'angry':
        segs = [((x0 - 4.5, by - 1.5), (x0 + 4.0, by + 2.2)), ((x1 - 4.0, by + 2.2), (x1 + 4.5, by - 1.5))]
    elif emo in ('sad', 'cry', 'nervous'):
        segs = [((x0 - 4.5, by + 1.2), (x0 + 4.0, by - 1.8)), ((x1 - 4.0, by - 1.8), (x1 + 4.5, by + 1.2))]
    elif emo == 'shock':
        segs = [((x0 - 4, by - 3), (x0 + 4, by - 3.5)), ((x1 - 4, by - 3.5), (x1 + 4, by - 3))]
    elif emo in ('smug', 'confused', 'suspicious') or (thick and emo == 'neutral'):
        segs = [((x0 - 4, by + 1), (x0 + 4, by + 1)), ((x1 - 4, by - 2.5), (x1 + 4, by - 1.5))]
    else:
        segs = [((x0 - 4, by), (x0 + 4, by - 0.8)), ((x1 - 4, by - 0.8), (x1 + 4, by))]
    for a, b in segs:
        ctx.move_to(*a); ctx.line_to(*b)
    ctx.stroke()

    mouth(ctx, st.get('mouth', 'closed'), emo, (4.5, HEAD[1] + 10))


def mouth(ctx, shape, emo, at):
    x, y = at
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    inside, tongue = (0.35, 0.05, 0.08), (0.95, 0.45, 0.5)
    if shape == 'closed':
        ctx.set_source_rgb(*INK); ctx.set_line_width(1.2)
        if emo == 'shock':
            ctx.save(); ctx.translate(x, y); ctx.scale(1, 1.2); ctx.arc(0, 0, 2.2, 0, 2 * math.pi); ctx.restore()
            fill_stroke(ctx, inside, 1.0); return
        if emo in ('happy', 'excited'):
            ctx.move_to(x - 5, y - 1.5); ctx.curve_to(x - 2, y + 3.5, x + 2, y + 3.5, x + 5, y - 1.5)
        elif emo == 'smug':
            ctx.move_to(x - 4, y + 0.5); ctx.curve_to(x, y + 1.5, x + 3, y, x + 5, y - 2.5)
        elif emo in ('sad', 'cry', 'angry'):
            ctx.move_to(x - 4.5, y + 1.8); ctx.curve_to(x - 1.5, y - 2, x + 1.5, y - 2, x + 4.5, y + 1.8)
        elif emo == 'nervous':
            ctx.move_to(x - 5, y)
            for i in range(1, 6):
                ctx.line_to(x - 5 + i * 2, y + (1.1 if i % 2 else -1.1))
        else:
            ctx.move_to(x - 3.5, y); ctx.curve_to(x - 1, y + 1, x + 1, y + 1, x + 3.5, y)
        ctx.stroke()
        return
    w, h = {'e': (5.8, 2.2), 'ai': (5.0, 3.8), 'o': (3.4, 4.2), 'u': (2.3, 2.8), 'wide': (7.5, 6.5)}.get(shape, (4, 3))
    ctx.save(); ctx.translate(x, y + h * 0.3); ctx.scale(w, h)
    ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
    ctx.set_source_rgb(*inside); ctx.fill_preserve()
    ctx.save(); ctx.clip()
    if shape in ('ai', 'wide', 'o'):
        ctx.save(); ctx.translate(x, y + h * 1.05); ctx.scale(w * 0.7, h * 0.5)
        ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
        ctx.set_source_rgb(*tongue); ctx.fill()
    if shape in ('wide', 'e', 'ai'):
        ctx.rectangle(x - w, y + h * 0.3 - h, 2 * w, h * 0.35)
        ctx.set_source_rgb(1, 1, 1); ctx.fill()
    ctx.restore()
    ctx.save(); ctx.translate(x, y + h * 0.3); ctx.scale(w, h)
    ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
    ctx.set_source_rgb(*INK); ctx.set_line_width(1.0); ctx.stroke()


# ---------------------------------------------------------------- efektler

def drop(ctx, x, y, s):
    ctx.new_path()
    ctx.move_to(x, y - 2.2 * s)
    ctx.curve_to(x + 1.6 * s, y - 0.2 * s, x + 1.4 * s, y + 1.2 * s, x, y + 1.2 * s)
    ctx.curve_to(x - 1.4 * s, y + 1.2 * s, x - 1.6 * s, y - 0.2 * s, x, y - 2.2 * s)
    ctx.close_path()


def overlay_fx(ctx, cid, c, st):
    t = st['t']
    emo = st['emotion']
    if emo == 'nervous':
        yy = HEAD[1] - 10 + (t * 14 % 8)
        drop(ctx, HEAD[0] - 16, yy, 2.2)
        fill_stroke(ctx, (0.55, 0.85, 1.0), 0.7)
    if emo == 'angry':
        ctx.save(); ctx.translate(HEAD[0] - 12, HEAD[1] - 16)
        k = 1 + 0.15 * math.sin(t * 18); ctx.scale(k, k)
        ctx.set_source_rgb(0.9, 0.1, 0.12); ctx.set_line_width(1.3)
        for a in range(4):
            ctx.save(); ctx.rotate(a * math.pi / 2)
            ctx.move_to(1.2, -3.5); ctx.curve_to(1.2, -1.2, 1.2, -1.2, 3.5, -1.2)
            ctx.restore()
        ctx.stroke(); ctx.restore()
    if emo == 'cry':  # fıskiye gözyaşı
        for side, ex in ((-1, -3.0), (1, 9.5)):
            for k in range(7):
                ph = (t * 2.2 + k / 7) % 1.0
                dx = side * (4 + 26 * ph) + 1.5
                dy = -7 * ph * 4 + 34 * ph * ph
                ctx.arc(ex + dx, HEAD[1] - 1 + dy, 1.6 - ph * 0.6, 0, 2 * math.pi)
                ctx.set_source_rgba(0.35, 0.7, 1.0, 0.95); ctx.fill()
    if emo in ('confused', 'shock'):
        sym = '?' if emo == 'confused' else '!'
        ctx.save()
        ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(15)
        ctx.translate(14, HEAD[1] - HEAD_R - 6 + math.sin(t * 8) * 1.2)
        ctx.move_to(0, 0); ctx.text_path(sym)
        ctx.set_source_rgb(1, 0.85, 0.1) if sym == '!' else ctx.set_source_rgb(1, 1, 1)
        ctx.fill_preserve(); ctx.set_source_rgb(*INK); ctx.set_line_width(1); ctx.stroke()
        ctx.restore()


# ---------------------------------------------------------------- karakter

def draw(ctx, cid, x, ground, s, facing, st):
    """st: hf hb ff fb drop emotion mouth blink t breath bob tilt lift bend
    -> öndeki elin ve ön omzun cihaz koordinatı (işaretçi çubuk için)."""
    c = CAST[cid]
    sc = s * c['scale']
    ctx.save()
    ctx.translate(x, ground)
    if st.get('tilt'):
        ctx.rotate(math.radians(st['tilt']) * facing)
    ctx.scale(sc * facing, sc)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    # zemin gölgesi
    ctx.save(); ctx.scale(1, 0.18); ctx.arc(0, 0, 17, 0, 2 * math.pi); ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.25); ctx.fill()

    drop_ = st.get('drop', 0)
    breath = st.get('breath', 1.0)
    ctx.translate(0, drop_ - st.get('lift', 0))

    for side, key in ((-1, 'fb'), (1, 'ff')):
        hip = (HIP[0] * side, HIP[1])
        tgt = st[key]
        tgt = (tgt[0], tgt[1] - drop_ + st.get('lift', 0))
        knee, foot = ik(hip, tgt, *LEG, lambda a, b: a if a[0] > b[0] else b)
        ctx.set_line_width(LIMB)
        limb_path(ctx, hip, knee, foot); ctx.set_source_rgb(*INK); ctx.stroke()
        ctx.save(); ctx.translate(foot[0] + 2.2, foot[1] - 1.2); ctx.scale(1, 0.55)
        ctx.arc(0, 0, 3.6, 0, 2 * math.pi); ctx.restore()
        ctx.set_source_rgb(*INK); ctx.fill()

    ctx.save()
    ctx.translate(0, -31); ctx.scale(1, breath); ctx.translate(0, 31)
    torso(ctx, cid, c)
    ctx.restore()

    ctx.save()
    ctx.translate(0, -(breath - 1) * 26 + st.get('bob', 0))
    ctx.translate(0, -58); ctx.rotate(math.radians(st.get('head_tilt', 0))); ctx.translate(0, 58)
    behind_head(ctx, cid, c)
    ctx.arc(*HEAD, HEAD_R, 0, 2 * math.pi)
    fill_stroke(ctx, c['skin'])
    ctx.save(); ctx.translate(HEAD[0] - HEAD_R + 1.5, HEAD[1] + 1); ctx.scale(0.7, 1)
    ctx.arc(0, 0, 3.4, 0, 2 * math.pi); ctx.restore()
    fill_stroke(ctx, c['skin'], 0.8)
    if st['emotion'] == 'angry':
        ctx.save()
        ctx.arc(*HEAD, HEAD_R - 0.6, 0, 2 * math.pi); ctx.clip()
        g = cairo.LinearGradient(0, HEAD[1] - HEAD_R, 0, HEAD[1] + 4)
        g.add_color_stop_rgba(0, 0.95, 0.1, 0.1, 0.7)
        g.add_color_stop_rgba(1, 0.95, 0.1, 0.1, 0.0)
        ctx.set_source(g); ctx.paint(); ctx.restore()
    hair_and_hats(ctx, cid, c)
    face(ctx, cid, c, st)
    overlay_fx(ctx, cid, c, st)
    ctx.restore()

    # kollar (en önde)
    shoulder_y = SHOULDER[1] - (breath - 1) * 20
    front = None
    for side, key in ((-1, 'hb'), (1, 'hf')):
        sh = (SHOULDER[0] * side, shoulder_y)
        tgt = st[key]
        bend = st.get('bend', 'out')
        if bend == 'down':
            pref = lambda a, b: a if a[1] > b[1] else b
        else:
            pref = (lambda a, b: a if a[0] > b[0] else b) if side > 0 else (lambda a, b: a if a[0] < b[0] else b)
        elbow, hand = ik(sh, tgt, *ARM, pref)
        ctx.set_line_width(LIMB)
        limb_path(ctx, sh, elbow, hand); ctx.set_source_rgb(*INK); ctx.stroke()
        ctx.arc(hand[0], hand[1], 2.6, 0, 2 * math.pi)
        fill_stroke(ctx, c['skin'], 0.9)
        if side > 0:
            front = (ctx.user_to_device(*hand), ctx.user_to_device(*sh))
    ctx.restore()
    return front


def local_target(x, ground, s, facing, cid, lift, point):
    """Ekrandaki bir noktayı karakterin yerel (sağa bakan) çerçevesine çevirir: kolu oraya uzatmak için."""
    sc = s * CAST[cid]['scale']
    return ((point[0] - x) / (sc * facing), (point[1] - ground) / sc + lift)


def pointer(ctx, hand, toward, length):
    """Charlie'nin işaretçi çubuğu: elden hedefe doğru."""
    dx, dy = toward[0] - hand[0], toward[1] - hand[1]
    d = max(1e-3, math.hypot(dx, dy))
    ux, uy = dx / d, dy / d
    L = min(length, d - 10)
    tip = (hand[0] + ux * L, hand[1] + uy * L)
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgb(*INK); ctx.set_line_width(13)
    ctx.move_to(*hand); ctx.line_to(*tip); ctx.stroke()
    ctx.set_source_rgb(0.62, 0.42, 0.22); ctx.set_line_width(8)
    ctx.move_to(*hand); ctx.line_to(*tip); ctx.stroke()
    ctx.arc(tip[0], tip[1], 9, 0, 2 * math.pi)
    fill_stroke(ctx, (0.95, 0.2, 0.2), 3)
    ctx.restore()
    return tip
