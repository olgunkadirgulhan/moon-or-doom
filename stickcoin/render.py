"""Video = replikler dizisi -> MP4. Her replik bir sahnede geçer:

  stage  tam ekran karakterler, mekan, konuşana kamera yakınlaşması
  chart  mum grafiği + seviye animasyonları, altta karakterler; Charlie'nin çubuğu anlatılan çizgiyi gösterir
  board  bilgi/ders panosu (boards.py), altta karakterler

Düzen: 'short' 1080x1920 (dikey), 'long' 1920x1080 (yatay, çok coinli uzun video).
Sahne/coin değişiminde kısa beyaz flaş + whoosh; sonda beğen/abone/zil kartı.
"""
import math
import random
import subprocess
import zlib
from pathlib import Path

import cairo
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from . import ROOT, audio, boards, endcard, rig, scenes, words
from .cast import CAST
from .chart import DOWN, UP, Chart

FPS = 30
FONT = str(ROOT / 'fonts' / 'LuckiestGuy-Regular.ttf')
LAYOUTS = {
    'short': dict(
        W=1080, H=1920, panel=(36, 300, 1008, 860), strip_top=1180, sub=(540, 1272, 1015, 62),
        chart_ground=1785, chart_s=4.5, chart_x={2: [(302, 1), (778, -1)], 3: [(220, 1), (540, -1), (860, -1)]},
        stage_ground=1600, stage_s=8.2, stage_x={2: [(0.3, 1), (0.7, -1)], 3: [(0.2, 1), (0.5, -1), (0.8, -1)]},
        stage_top=260, stage_sub=(540, 690, 1000, 66), banner='tall', endcard_y=560, hook_y=420),
    'long': dict(
        W=1920, H=1080, panel=(40, 130, 1180, 830), strip_top=520, sub=(630, 1018, 1180, 46),
        chart_ground=1040, chart_s=5.0, chart_x={2: [(1430, -1), (1750, -1)], 3: [(1380, -1), (1600, -1), (1820, -1)]},
        stage_ground=1010, stage_s=7.4, stage_x={2: [(0.33, 1), (0.67, -1)], 3: [(0.22, 1), (0.5, -1), (0.78, -1)]},
        stage_top=120, stage_sub=(960, 205, 1500, 58), banner='wide', endcard_y=330, hook_y=None),
}
TRANSITION = 0.12
ACT_SFX = {'show': ('whoosh', 0.0, 0.5), 'draw_resistance': ('pop', 0.6, 0.8), 'draw_support': ('pop', 0.6, 0.8),
           'highlight_scenario_up': ('cash', 0.5, 0.75), 'highlight_scenario_down': ('thud', 0.6, 0.9)}


def log(m):
    print(f'[render] {m}', flush=True)


def stable(x):
    return zlib.crc32(str(x).encode())


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return a + (b - a) * k


# ------------------------------------------------------------------ metin (PIL -> cairo)

def pil_to_surface(img):
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    alpha = a[:, :, 3:4] / 255.0
    rgb = a[:, :, :3] * alpha
    out = np.empty(a.shape, np.uint8)
    out[:, :, 0] = rgb[:, :, 2]; out[:, :, 1] = rgb[:, :, 1]; out[:, :, 2] = rgb[:, :, 0]
    out[:, :, 3] = a[:, :, 3]
    h, w = out.shape[:2]
    return cairo.ImageSurface.create_for_data(memoryview(np.ascontiguousarray(out)), cairo.FORMAT_ARGB32, w, h, w * 4)


def text_block(words_, size, maxw, hi=None, hi_color=(255, 214, 0), color=(255, 255, 255), stroke=(0, 0, 0),
               stroke_w=None):
    font = ImageFont.truetype(FONT, size)
    tmp = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    rows, cur = [], []
    for i, w in enumerate(words_):
        test = ' '.join(x for _, x in cur + [(i, w)])
        if cur and tmp.textlength(test, font=font) > maxw:
            rows.append(cur); cur = []
        cur.append((i, w))
    if cur:
        rows.append(cur)
    sw = stroke_w if stroke_w is not None else max(3, size // 10)
    lh = int(size * 1.12)
    widths = [tmp.textlength(' '.join(w for _, w in r), font=font) for r in rows]
    Wd = int(max(widths) + 2 * sw + 10)
    Hd = int(lh * len(rows) + 2 * sw + size * 0.25)
    img = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    space = tmp.textlength(' ', font=font)
    for r, row in enumerate(rows):
        x = (Wd - widths[r]) / 2
        for i, w in row:
            d.text((x, sw + r * lh), w, font=font, fill=hi_color if i == hi else color, stroke_width=sw, stroke_fill=stroke)
            x += tmp.textlength(w, font=font) + space
    return img


def logo_surface(data, size):
    img = None
    if data['coin'].get('logo') and Path(data['coin']['logo']).exists():
        img = Image.open(data['coin']['logo']).convert('RGBA').resize((size, size), Image.LANCZOS)
    if img is None:  # logo yoksa sembol harfli daire
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((0, 0, size - 1, size - 1), fill=(90, 110, 160, 255))
        f = ImageFont.truetype(FONT, int(size * 0.42))
        t = data['coin']['symbol'][:3]
        d.text(((size - d.textlength(t, font=f)) / 2, size * 0.25), t, font=f, fill=(255, 255, 255))
    ring = Image.new('RGBA', (size + 16, size + 16), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, size + 15, size + 15), fill=(255, 255, 255, 255))
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    ring.paste(img, (8, 8), Image.composite(img, Image.new('RGBA', img.size, (0, 0, 0, 0)), mask))
    return pil_to_surface(ring)


# ------------------------------------------------------------------ zaman çizelgesi + ses

def build_timeline(video, workdir, speed_mul=1.0):
    """video: {'id', 'layout', 'coins': {key: data}, 'cast': [...], 'lines': [...], 'mood'}"""
    t = 0.3
    voices, effects, mask = [], [], [(0, 0)]
    lines, prev = [], None
    n = len(video['lines'])
    short = video['layout'] == 'short'
    for i, line in enumerate(video['lines']):
        L = dict(line, start=t)
        key = (L['scene'], L.get('coin'), L.get('board') if L['scene'] == 'board' else None)
        if prev is not None and key[:2] != prev[:2]:
            effects.append((t, audio.sfx('whoosh', i), 0.35))
        prev = key
        samples, wds = audio.speak(line['char'], line['tokens'], line.get('emotion', 'neutral'), speed_mul)
        L['speech'] = (t + 0.05, t + 0.05 + len(samples) / audio.SR)
        L['words'] = wds
        hop = audio.SR // FPS
        env = np.array([np.sqrt(np.mean(samples[k * hop:(k + 1) * hop] ** 2)) if k * hop < len(samples) else 0
                        for k in range(len(samples) // hop + 1)])
        L['env'] = env / (env.max() + 1e-6)
        voices.append((L['speech'][0], samples, 1.0))
        mask += [(L['speech'][0] - 0.05, 0), (L['speech'][0], 1), (L['speech'][1], 1), (L['speech'][1] + 0.05, 0)]
        act = line.get('chart_action', 'none')
        if act != 'none':
            L['act_at'] = t + (0.0 if act == 'show' else 0.35)
            name, dt, gain = ACT_SFX[act]
            effects.append((L['act_at'] + dt, audio.sfx(name, i), gain))
        if i == 0 and short:
            effects.append((0.0, audio.sfx('rocket' if video['mood'] == 'bullish' else 'sting', 1), 0.55))
        if line.get('jump'):
            L['jump_at'] = t
            effects.append((t, audio.sfx('boing', i), 0.5))
        if line['char'] != 'charlie' and line.get('emotion') == 'cry':
            effects.append((L['speech'][1], audio.sfx('cry', i), 0.6))
        if short and i == n - 2 and line['char'] == 'charlie':
            effects.append((L['speech'][1] + 0.05, audio.sfx('rimshot', i), 0.7))
        gap = 0.18 if short else 0.3  # Shorts: sıkı tempo (izlenme süresi)
        if i + 1 < n and video['lines'][i + 1].get('segment_start'):
            gap = 0.7
        t = L['speech'][1] + gap
        L['end'] = t
        lines.append(L)
    end0 = t + 0.4
    for dt, name in ((endcard.CLICK_LIKE, 'pop'), (endcard.CLICK_SUB, 'pop'), (endcard.CLICK_BELL, 'ding')):
        effects.append((end0 + dt, audio.sfx(name, 90), 0.55))
    total = end0 + endcard.DUR
    mt = np.array([m[0] for m in mask] + [total]); mv = np.array([m[1] for m in mask] + [0])
    order = np.argsort(mt, kind='stable')
    track = audio.music(total + 1, seed=stable(video['id']) % 10_000, mood=video['mood'])
    stereo = audio.mix(total, voices, effects, track, (mt[order], mv[order]))
    wav = Path(workdir) / 'audio.wav'
    sf.write(str(wav), stereo, audio.SR)
    return lines, total, end0, wav


# ------------------------------------------------------------------ kare çizimi

class Actor:
    def __init__(self, cid, pose, emotion, seed):
        self.cid, self.pose, self.emotion = cid, pose, emotion
        tg = rig.pose_targets(pose)
        self.cur = {k: tg[k] for k in ('hf', 'hb', 'ff', 'fb')}
        self.rng = random.Random(seed)
        self.next_blink = self.rng.uniform(0.5, 3)


class Renderer:
    def __init__(self, video, lines, total, end0):
        self.v, self.lines, self.total, self.end0 = video, lines, total, end0
        self.Lo = LAYOUTS[video['layout']]
        self.W, self.H = self.Lo['W'], self.Lo['H']
        self.coins = video['coins']
        rnd = random.Random(stable(video['id']))
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.W, self.H)
        self.ctx = cairo.Context(self.surf)
        self.charts = {k: Chart(d, self.Lo['panel']) for k, d in self.coins.items()}
        self.logos = {k: (logo_surface(d, 120 if self.Lo['banner'] == 'tall' else 84),
                          logo_surface(d, 300 if self.Lo['banner'] == 'tall' else 260)) for k, d in self.coins.items()}
        # mekanlar: grafik/pano altı şerit + tam ekran sahne (coin başına ruh haline göre)
        self.place = {k: scenes.for_mood(d.get('change_7d_pct') if video['layout'] == 'long' and d.get('change_7d_pct')
                                         is not None else d['change_24h_pct'], rnd) for k, d in self.coins.items()}
        self.bg_cache = {}
        n = len(video['cast'])
        self.actors = {cid: Actor(cid, 'hips' if cid == 'moon_max' else 'arms_crossed' if cid == 'bear_betty' else 'standing',
                                  'excited' if cid == 'moon_max' else 'suspicious' if cid == 'bear_betty' else 'neutral', i)
                       for i, cid in enumerate(video['cast'])}
        self.n = n
        self.acts = {}
        for L in lines:
            if 'act_at' in L:
                self.acts.setdefault(L['coin'], {})[L['chart_action']] = L['act_at']
        self.scene_start, self.cache, self.prev = {}, {}, None
        start, prev = None, None
        for L in lines:  # her replik için bulunduğu sahnenin başlangıcı (pano animasyonu, flaş)
            key = (L['scene'], L.get('coin'), L.get('board'))
            if key != prev:
                start = L['start']
            L['scene_start'] = start
            prev = key
        self.shot = {id(L): rnd.choice(['wide', 'push', 'push', 'punch']) for L in lines}

    def bg(self, kind, coin):
        key = (kind, coin)
        if key not in self.bg_cache:
            if len(self.bg_cache) > 6:
                self.bg_cache.clear()
            Lo = self.Lo
            if kind == 'stage':
                self.bg_cache[key] = scenes.render(self.place[coin], self.W, self.H, Lo['stage_ground'], Lo['stage_top'],
                                                   seed=stable((self.v['id'], coin, 's')) % 1000)
            else:
                self.bg_cache[key] = scenes.render(self.place[coin], self.W, self.H, Lo['chart_ground'], Lo['strip_top'],
                                                   seed=stable((self.v['id'], coin)) % 1000)
        return self.bg_cache[key]

    def text(self, key, fn):
        if key not in self.cache:
            if len(self.cache) > 300:
                self.cache.clear()
            self.cache[key] = pil_to_surface(fn())
        return self.cache[key]

    def paste(self, surf, x, y, scale=1.0, anchor='center', alpha=1.0):
        ctx = self.ctx
        ctx.save()
        ctx.translate(x, y); ctx.scale(scale, scale)
        dx = {'center': -surf.get_width() / 2, 'left': 0, 'right': -surf.get_width()}[anchor]
        ctx.set_source_surface(surf, dx, -surf.get_height() / 2)
        ctx.paint_with_alpha(alpha)
        ctx.restore()

    # ---- üst bant
    def banner(self, coin, t, compact=False):
        d = self.coins[coin]
        up = d['change_24h_pct'] >= 0
        col = tuple(int(v * 255) for v in (UP if up else DOWN))
        k = ease(t / 1.2) if self.v['layout'] == 'short' else 1.0
        chg = f"{'+' if up else '-'}{abs(d['change_24h_pct'] * k):.1f}% 24H"
        small = self.logos[coin][0]
        if self.Lo['banner'] == 'tall' and not compact:
            W = self.W
            self.paste(small, 60, 175, anchor='left')
            self.paste(self.text(('sym', coin), lambda: text_block([d['coin']['symbol']], 96, 600)), 225, 150, anchor='left')
            self.paste(self.text(('name', coin), lambda: text_block(d['coin']['name'].upper().split(), 38, 420,
                                                                    color=(170, 185, 215), stroke_w=0)), 230, 222, anchor='left')
            self.paste(self.text(('price', coin), lambda: text_block([words.price_text(d['price'])], 64, 500)),
                       W - 50, 140, anchor='right')
            self.paste(self.text(('chg', chg), lambda: text_block(chg.split(), 50, 500, color=col, stroke_w=4)),
                       W - 50, 215, anchor='right')
            return
        # kompakt: logo + sembol + % (sahne üstü ya da yatay düzen)
        y = 80 if self.Lo['banner'] == 'tall' else 66
        x = 40
        self.paste(small, x, y, 0.8 if self.Lo['banner'] == 'tall' else 1.0, anchor='left')
        x += small.get_width() * (0.8 if self.Lo['banner'] == 'tall' else 1.0) + 18
        sym = self.text(('csym', coin), lambda: text_block([d['coin']['symbol']], 64, 600))
        self.paste(sym, x, y, anchor='left')
        x += sym.get_width() + 18
        if self.v['layout'] == 'long' and d.get('change_7d_pct') is not None:
            c7 = d['change_7d_pct']
            chg = f"{'+' if c7 >= 0 else '-'}{abs(c7):.1f}% 7D"
            col = tuple(int(v * 255) for v in (UP if c7 >= 0 else DOWN))
        self.paste(self.text(('cchg', chg), lambda: text_block(chg.split(), 44, 600, color=col, stroke_w=4)), x, y + 4,
                   anchor='left')
        if self.v['layout'] == 'long':
            self.paste(self.text(('cprice', coin), lambda: text_block([words.price_text(d['price'])], 44, 400)),
                       self.W - 40, y, anchor='right')

    def hook_sticker(self, L, t):
        """Shorts'un ilk saniyeleri: dev logo + % değişim (sahne üstünde)."""
        if self.Lo['hook_y'] is None or L is not self.lines[0]:
            return
        d = self.coins[L['coin']]
        up = d['change_24h_pct'] >= 0
        a = 1 - ease((t - (L['end'] - 0.3)) / 0.3)
        if a <= 0:
            return
        pop = 0.6 + 0.4 * ease(t / 0.35) + 0.03 * math.sin(t * 8)
        cx, cy = self.W / 2, self.Lo['hook_y']
        self.paste(self.logos[L['coin']][1], cx - 230, cy, pop * 0.7, alpha=a)
        txt = f"{'+' if up else '-'}{abs(d['change_24h_pct'] * ease(t / 1.0)):.1f}%"
        col = tuple(int(v * 255) for v in (UP if up else DOWN))
        self.paste(self.text(('big', txt), lambda: text_block([txt], 150, 900, color=col, stroke_w=10)),
                   cx + 110, cy, pop, alpha=a)

    def subtitle(self, L, t, stage):
        if 'words' not in L or t > L['speech'][1] + 0.25:
            return
        x, y, maxw, size = self.Lo['stage_sub'] if stage else self.Lo['sub']
        rel = t - L['speech'][0]
        wi = 0
        for i, w in enumerate(L['words']):
            if rel >= w['start']:
                wi = i
        acc = tuple(int(v * 255) for v in CAST[L['char']]['accent'])
        surf = self.text((id(L), wi, stage), lambda: text_block([w['text'].upper() for w in L['words']], size, maxw,
                                                               hi=wi, hi_color=acc))
        self.paste(surf, x, y, 0.85 + 0.15 * ease(rel / 0.12))

    def find(self, t):
        cur = self.lines[0]
        for L in self.lines:
            if t >= L['start']:
                cur = L
        return cur

    def positions(self, stage):
        Lo = self.Lo
        n = min(3, max(2, self.n))
        if stage:
            return [(fx * self.W, f) for fx, f in Lo['stage_x'][n]], Lo['stage_ground'], Lo['stage_s']
        return Lo['chart_x'][n], Lo['chart_ground'], Lo['chart_s']

    def draw_actors(self, L, t, stage, focus):
        ctx = self.ctx
        slots, ground, s = self.positions(stage)
        order = ['charlie'] + [c for c in self.v['cast'] if c != 'charlie']
        for i, cid in enumerate(order):
            a = self.actors[cid]
            x, facing = slots[i]
            speaking = L['char'] == cid and L['speech'][0] <= t < L['speech'][1]
            tg = dict(rig.pose_targets(a.pose))
            lift = 0.0
            if L['char'] == cid and 'jump_at' in L and 0 <= t - L['jump_at'] < 0.75:
                lift = math.sin(math.pi * (t - L['jump_at']) / 0.75) * 26
                tg = dict(rig.pose_targets('celebrate'))
            pointing = cid == 'charlie' and not stage and L['scene'] == 'chart' and a.pose == 'pointing' and focus
            if pointing:
                tp = rig.local_target(x, ground, s, facing, cid, lift, focus)
                sh = rig.SHOULDER
                dx, dy = tp[0] - sh[0], tp[1] - sh[1]
                dl = max(1e-3, math.hypot(dx, dy))
                tg['hf'] = (sh[0] + dx / dl * 25.5, sh[1] + dy / dl * 25.5)
            for k in ('hf', 'hb', 'ff', 'fb'):
                a.cur[k] = (lerp(a.cur[k][0], tg[k][0], 0.3), lerp(a.cur[k][1], tg[k][1], 0.3))
            blink = 0
            if t >= a.next_blink:
                blink = 1
                if t >= a.next_blink + 0.12:
                    a.next_blink = t + a.rng.uniform(2.5, 5)
            mouth, bob, head_tilt = 'closed', 0.0, 0.0
            if speaking:
                j = int((t - L['speech'][0]) * FPS)
                lvl = L['env'][min(j, len(L['env']) - 1)]
                bob = -lvl * 1.5
                mouth = mouth_shape(lvl, L, t - L['speech'][0], a.emotion)
                head_tilt = 2.5 * math.sin(t * 7)
            st = dict(a.cur)
            st.update(emotion=a.emotion, mouth=mouth, blink=blink, t=t, bob=bob, head_tilt=head_tilt, lift=lift,
                      breath=1 + 0.012 * math.sin(t * math.pi + stable(cid) % 7), bend=tg.get('bend', 'out'),
                      look=(1.6, -1.2) if pointing else (1.2, 0))
            front = rig.draw(ctx, cid, x, ground, s, facing, st)
            if cid == 'charlie' and front and not stage and (pointing or a.pose in ('standing', 'hips')):
                hand = front[0]
                rig.pointer(ctx, hand, focus if pointing else (hand[0] + 70 * facing, hand[1] - 200),
                            240 if pointing else 150)

    def frame(self, t):
        ctx, W, H = self.ctx, self.W, self.H
        L = self.find(t)
        if L is not self.prev:
            a = self.actors[L['char']]
            a.emotion = L.get('emotion') or a.emotion
            if L.get('pose'):
                a.pose = L['pose']
            self.prev = L
        coin, scene = L['coin'], L['scene']
        stage = scene == 'stage'
        if stage:
            # kamera: konuşanın kafasına yakınlaş
            slots, ground, s = self.positions(True)
            order = ['charlie'] + [c for c in self.v['cast'] if c != 'charlie']
            sx = slots[order.index(L['char'])][0]
            hy = ground - 80 * s
            k = (t - L['start']) / max(0.3, L['end'] - L['start'])
            shot = self.shot[id(L)]
            z = {'wide': 1.0 + 0.03 * k, 'push': 1.0 + 0.14 * ease(k),
                 'punch': lerp(1.05, 1.28, ease((t - L['start']) / 0.2)) + 0.03 * k}[shot]
            ctx.save()
            ctx.translate(sx, hy); ctx.scale(z, z); ctx.translate(-sx, -hy)
            ctx.set_source_surface(self.bg('stage', coin), 0, 0); ctx.paint()
            scenes.dynamic(ctx, self.place[coin], W, self.Lo['stage_ground'], self.Lo['stage_top'], t)
            self.draw_actors(L, t, True, None)
            ctx.restore()
            self.banner(coin, t, compact=True)
            self.hook_sticker(L, t)
        else:
            ctx.set_source_surface(self.bg('panel', coin), 0, 0); ctx.paint()
            scenes.dynamic(ctx, self.place[coin], W, self.Lo['chart_ground'], self.Lo['strip_top'], t)
            self.banner(coin, t)
            focus = None
            if scene == 'chart':
                acts = self.acts.get(coin, {})
                started = {k2: v for k2, v in acts.items() if t >= v}
                active = L.get('chart_action') if L.get('chart_action') != 'none' else None
                self.charts[coin].draw(ctx, {'started': started, 'active': active}, t)
                focus_act = max(started, key=started.get) if started else None
                focus = self.charts[coin].focus(focus_act) if focus_act else None
            else:
                boards.draw(ctx, L.get('board') or 'stats', self.Lo['panel'], self.coins[coin], t - L['scene_start'],
                            self.logos[coin][1], L.get('label', ''))
            self.draw_actors(L, t, False, focus)
        self.subtitle(L, t, stage)
        if 0 <= t - L['scene_start'] < TRANSITION and L['scene_start'] > 0.3:
            ctx.set_source_rgba(1, 1, 1, 0.8 * (1 - (t - L['scene_start']) / TRANSITION)); ctx.paint()
        if t >= self.end0:
            lt = t - self.end0
            ctx.set_source_rgba(0, 0, 0, 0.45 * ease(lt / 0.35)); ctx.paint()
            card = pil_to_surface(endcard.layer(W, lt, 'MOON OR DOOM · TOP GAINER & LOSER DAILY'))
            ctx.set_source_surface(card, 0, self.Lo['endcard_y']); ctx.paint()
        if t > self.total - 0.3:
            ctx.set_source_rgba(0, 0, 0, ease((t - (self.total - 0.3)) / 0.3) * 0.6); ctx.paint()
        self.surf.flush()


def mouth_shape(lvl, L, rel, emo):
    if lvl < 0.13:
        return 'closed'
    if lvl > 0.8 and emo in ('angry', 'shock', 'excited', 'cry'):
        return 'wide'
    word = L['words'][0]
    for w in L['words']:
        if rel >= w['start']:
            word = w
    letters = [c for c in word.get('say', word['text']).lower() if c.isalpha()] or ['a']
    p = (rel - word['start']) / max(0.05, word['end'] - word['start'])
    ch = letters[min(len(letters) - 1, int(p * len(letters)))]
    vow = [c for c in letters if c in 'aeiouy']
    if ch not in 'aeiouwy' and vow:
        ch = vow[min(len(vow) - 1, int(p * len(vow)))]
    shape = {'a': 'ai', 'i': 'ai', 'e': 'e', 'y': 'e', 'o': 'o', 'u': 'u', 'w': 'u'}.get(ch, 'e')
    if lvl < 0.3:
        return 'e' if shape != 'u' else 'u'
    return shape


# ------------------------------------------------------------------ giriş noktası

def render(video, out_dir, preview_png=None):
    """-> (mp4, süre, bölüm başlangıçları [(saniye, başlık)])"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # uzun video: biraz daha sakin tempo (anlatım), Shorts: config hızı
    lines, total, end0, wav = build_timeline(video, out_dir, speed_mul=0.94 if video['layout'] == 'long' else 1.0)
    if video['layout'] == 'short' and total > 58.5:
        k = min(1.35, total / 57.0)
        log(f'{total:.1f}s too long, re-voicing at x{k:.2f}')
        lines, total, end0, wav = build_timeline(video, out_dir, speed_mul=k)
    log(f'timeline {total:.1f}s, {len(lines)} lines')
    R = Renderer(video, lines, total, end0)
    Lo = LAYOUTS[video['layout']]
    mp4 = out_dir / 'video.mp4'
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f"{Lo['W']}x{Lo['H']}",
           '-r', str(FPS), '-i', '-', '-i', str(wav), '-map', '0:v', '-map', '1:a',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', str(mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(total * FPS)
    acts = R.acts.get(lines[0]['coin'], {})
    snap = min(n - 1, int((acts.get('highlight_scenario_down', acts.get('draw_support', total * 0.5)) + 1.2) * FPS))
    for i in range(n):
        t = i / FPS
        R.frame(t)
        proc.stdin.write(bytes(R.surf.get_data()))
        if preview_png and i == snap:
            R.surf.write_to_png(str(preview_png))
        if i % (FPS * 20) == 0:
            log(f'frame {i}/{n}')
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    chapters = [(L['start'], L['chapter']) for L in lines if L.get('chapter')]
    return mp4, total, chapters
