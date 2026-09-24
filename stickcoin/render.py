"""Senaryo + veri -> 50 sn 9:16 MP4 (Bölüm 4 düzeni).

┌ üst bant: logo, sembol, fiyat, 24s % (sayarak gelir)
├ mum grafiği (üst 2/3): seviyeler senaryodaki chart_action ile çizilir
├ altyazı (kelime vurgulu)
└ karakterler + ruh haline göre sahne (alt 1/3); Charlie'nin çubuğu anlatılan çizgiyi gösterir
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

from . import ROOT, audio, endcard, rig, scenes, words
from .cast import CAST
from .chart import Chart, DOWN, UP

FPS = 30
W, H = 1080, 1920
FONT = str(ROOT / 'fonts' / 'LuckiestGuy-Regular.ttf')
CHART_RECT = (36, 300, W - 72, 860)
SCENE_TOP = CHART_RECT[1] + CHART_RECT[3] + 20
SUB_Y = SCENE_TOP + 92
GROUND, S = 1785, 4.5
POS = {'charlie': (0.28, 1), 'side': (0.72, -1)}
LEVEL_SFX = {'show': ('whoosh', 0.0, 0.5), 'draw_resistance': ('pop', 0.6, 0.8), 'draw_support': ('pop', 0.6, 0.8),
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

def build_timeline(sc, data, workdir, speed_mul=1.0):
    side = data['sidekick']
    bull = side == 'moon_max'
    t = 0.3
    voices, effects, mask = [], [], [(0, 0)]
    lines = []
    n = len(sc['lines'])
    for i, line in enumerate(sc['lines']):
        L = dict(line, start=t)
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
            name, dt, gain = LEVEL_SFX[act]
            effects.append((L['act_at'] + dt, audio.sfx(name, i), gain))
        if i == 0:
            effects.append((0.0, audio.sfx('rocket' if bull else 'sting', 1), 0.55))
        if line.get('jump'):
            L['jump_at'] = t
            effects.append((t, audio.sfx('boing', i), 0.5))
        if line['char'] == side and line.get('emotion') == 'cry':
            effects.append((L['speech'][1], audio.sfx('cry', i), 0.6))
        if i == n - 2 and line['char'] == 'charlie':
            effects.append((L['speech'][1] + 0.05, audio.sfx('rimshot', i), 0.7))
        t = L['speech'][1] + (0.9 if i == n - 3 else 0.25)
        L['end'] = t
        lines.append(L)
    end0 = t + 0.4  # kapanış kartı: beğen / abone ol / zil
    for dt, name in ((endcard.CLICK_LIKE, 'pop'), (endcard.CLICK_SUB, 'pop'), (endcard.CLICK_BELL, 'ding')):
        effects.append((end0 + dt, audio.sfx(name, 90), 0.55))
    total = end0 + endcard.DUR
    mt = np.array([m[0] for m in mask] + [total]); mv = np.array([m[1] for m in mask] + [0])
    order = np.argsort(mt, kind='stable')
    track = audio.music(total + 1, seed=stable(sc.get('id', data['id'])) % 10_000, mood=data['mood'])
    stereo = audio.mix(total, voices, effects, track, (mt[order], mv[order]))
    wav = Path(workdir) / 'audio.wav'
    sf.write(str(wav), stereo, audio.SR)
    return lines, total, end0, wav


# ------------------------------------------------------------------ kare çizimi

class Actor:
    def __init__(self, cid, x, facing, pose, emotion, seed):
        self.cid, self.x, self.facing = cid, x, facing
        self.pose, self.emotion = pose, emotion
        tg = rig.pose_targets(pose)
        self.cur = {k: tg[k] for k in ('hf', 'hb', 'ff', 'fb')}
        self.rng = random.Random(seed)
        self.next_blink = self.rng.uniform(0.5, 3)


class Renderer:
    def __init__(self, sc, data, lines, total, end0):
        self.sc, self.d, self.lines, self.total, self.end0 = sc, data, lines, total, end0
        rnd = random.Random(stable(data['id']))
        self.scene = scenes.for_mood(data['change_24h_pct'], rnd)
        self.bg = scenes.render(self.scene, W, H, GROUND, SCENE_TOP, seed=stable(data['id']) % 1000)
        self.chart = Chart(data, CHART_RECT)
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.ctx = cairo.Context(self.surf)
        side = data['sidekick']
        self.actors = {
            'charlie': Actor('charlie', POS['charlie'][0] * W, POS['charlie'][1], 'standing', 'neutral', 1),
            side: Actor(side, POS['side'][0] * W, POS['side'][1], 'hips' if side == 'moon_max' else 'arms_crossed',
                        'excited' if side == 'moon_max' else 'suspicious', 2),
        }
        self.cache = {}
        self.logo_small = logo_surface(data, 130)
        self.logo_big = logo_surface(data, 300)
        self.acts = {L['chart_action']: L['act_at'] for L in lines if 'act_at' in L}
        self.show_at = self.acts.get('show', 3.0)
        self.prev = None

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
    def banner(self, t):
        d = self.d
        up = d['change_24h_pct'] >= 0
        self.paste(self.logo_small, 60, 175, anchor='left')
        self.paste(self.text('sym', lambda: text_block([d['coin']['symbol']], 96, 600)), 225, 150, anchor='left')
        self.paste(self.text('name', lambda: text_block(d['coin']['name'].upper().split(), 38, 420,
                                                        color=(170, 185, 215), stroke_w=0)), 230, 222, anchor='left')
        self.paste(self.text('price', lambda: text_block([words.price_text(d['price'])], 64, 500)), W - 50, 140,
                   anchor='right')
        k = ease(t / 1.2)
        shown = d['change_24h_pct'] * k
        sign = '+' if up else '-'
        txt = f'{sign}{abs(shown):.1f}% 24H'
        col = tuple(int(v * 255) for v in (UP if up else DOWN))
        self.paste(self.text(('chg', txt), lambda: text_block(txt.split(), 50, 500, color=col, stroke_w=4)),
                   W - 50, 215, anchor='right')

    # ---- grafik öncesi hook kartı
    def hook_card(self, t):
        a = 1 - ease((t - self.show_at) / 0.4)
        if a <= 0:
            return
        x0, y0, w, h = CHART_RECT
        cx, cy = x0 + w / 2, y0 + h * 0.42
        pop = 0.6 + 0.4 * ease(t / 0.35) + 0.03 * math.sin(t * 8)
        self.paste(self.logo_big, cx, cy - 60, pop, alpha=a)
        d = self.d
        up = d['change_24h_pct'] >= 0
        txt = f"{'+' if up else '-'}{abs(d['change_24h_pct'] * ease(t / 1.0)):.1f}%"
        col = tuple(int(v * 255) for v in (UP if up else DOWN))
        self.paste(self.text(('big', txt), lambda: text_block([txt], 170, 900, color=col, stroke_w=10)),
                   cx, cy + 210, pop, alpha=a)

    def subtitle(self, L, t):
        if 'words' not in L or t > L['speech'][1] + 0.25:
            return
        rel = t - L['speech'][0]
        wi = 0
        for i, w in enumerate(L['words']):
            if rel >= w['start']:
                wi = i
        acc = tuple(int(v * 255) for v in CAST[L['char']]['accent'])
        surf = self.text((id(L), wi), lambda: text_block([w['text'].upper() for w in L['words']], 62, W * 0.94,
                                                         hi=wi, hi_color=acc))
        self.paste(surf, W / 2, SUB_Y, 0.85 + 0.15 * ease(rel / 0.12))

    def find(self, t):
        cur = None
        for L in self.lines:
            if t >= L['start']:
                cur = L
        return cur

    def frame(self, t):
        ctx = self.ctx
        L = self.find(t)
        if L is not None and L is not self.prev:
            a = self.actors[L['char']]
            a.emotion = L.get('emotion') or a.emotion
            if L.get('pose'):
                a.pose = L['pose']
            self.prev = L
        ctx.set_source_surface(self.bg, 0, 0); ctx.paint()
        scenes.dynamic(ctx, self.scene, W, GROUND, SCENE_TOP, t)
        self.banner(t)
        started = {k: v for k, v in self.acts.items() if t >= v}
        active = L.get('chart_action') if L is not None and L.get('chart_action') != 'none' else None
        self.chart.draw(ctx, {'started': started, 'active': active}, t)
        self.hook_card(t)

        # Charlie'nin çubuğu: son başlayan grafik aksiyonunu gösterir
        focus_act = max(started, key=started.get) if started else None
        focus = self.chart.focus(focus_act) if focus_act else None
        for cid, a in self.actors.items():
            speaking = L is not None and L['char'] == cid and L['speech'][0] <= t < L['speech'][1]
            tg = dict(rig.pose_targets(a.pose))
            lift = 0.0
            if L is not None and L['char'] == cid and 'jump_at' in L and 0 <= t - L['jump_at'] < 0.75:
                lift = math.sin(math.pi * (t - L['jump_at']) / 0.75) * 26
                tg = dict(rig.pose_targets('celebrate'))
            pointing = cid == 'charlie' and a.pose == 'pointing' and focus is not None
            if pointing:
                tp = rig.local_target(a.x, GROUND, S, a.facing, cid, lift, focus)
                sh = rig.SHOULDER
                dx, dy = tp[0] - sh[0], tp[1] - sh[1]
                dl = max(1e-3, math.hypot(dx, dy))
                tg['hf'] = (sh[0] + dx / dl * 25.5, sh[1] + dy / dl * 25.5)
            for key in ('hf', 'hb', 'ff', 'fb'):
                a.cur[key] = (lerp(a.cur[key][0], tg[key][0], 0.3), lerp(a.cur[key][1], tg[key][1], 0.3))
            blink = 0
            if t >= a.next_blink:
                blink = 1
                if t >= a.next_blink + 0.12:
                    a.next_blink = t + a.rng.uniform(2.5, 5)
            mouth, bob, head_tilt = 'closed', 0.0, 0.0
            if speaking:
                i = int((t - L['speech'][0]) * FPS)
                lvl = L['env'][min(i, len(L['env']) - 1)]
                bob = -lvl * 1.5
                mouth = mouth_shape(lvl, L, t - L['speech'][0], a.emotion)
                head_tilt = 2.5 * math.sin(t * 7)
            st = dict(a.cur)
            st.update(emotion=a.emotion, mouth=mouth, blink=blink, t=t, bob=bob, head_tilt=head_tilt, lift=lift,
                      breath=1 + 0.012 * math.sin(t * math.pi + stable(cid) % 7), bend=tg.get('bend', 'out'),
                      look=(1.6, -1.2) if cid == 'charlie' and pointing else (1.2, 0))
            front = rig.draw(ctx, cid, a.x, GROUND, S, a.facing, st)
            if cid == 'charlie' and front and (pointing or a.pose in ('standing', 'hips')):
                hand = front[0]
                rig.pointer(ctx, hand, focus if pointing else (hand[0] + 70, hand[1] - 200), 240 if pointing else 150)
        if L is not None:
            self.subtitle(L, t)
        if t >= self.end0:
            lt = t - self.end0
            ctx.set_source_rgba(0, 0, 0, 0.45 * ease(lt / 0.35)); ctx.paint()
            card = pil_to_surface(endcard.layer(W, lt, 'MOON OR DOOM · TOP GAINER & LOSER 3X DAILY'))
            ctx.set_source_surface(card, 0, 560); ctx.paint()
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

def render(sc, data, out_dir, preview_png=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines, total, end0, wav = build_timeline(sc, data, out_dir)
    if total > 58.5:
        k = min(1.35, total / 57.0)
        log(f'{total:.1f}s too long, re-voicing at x{k:.2f}')
        lines, total, end0, wav = build_timeline(sc, data, out_dir, speed_mul=k)
    log(f'timeline {total:.1f}s, {len(lines)} lines')
    R = Renderer(sc, data, lines, total, end0)
    mp4 = out_dir / 'video.mp4'
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-i', str(wav), '-map', '0:v', '-map', '1:a',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', str(mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(total * FPS)
    snap = min(n - 1, int((R.acts.get('highlight_scenario_down', R.acts.get('draw_support', total * 0.5)) + 1.2) * FPS))
    for i in range(n):
        t = i / FPS
        R.frame(t)
        proc.stdin.write(bytes(R.surf.get_data()))
        if preview_png and i == snap:
            R.surf.write_to_png(str(preview_png))
        if i % (FPS * 10) == 0:
            log(f'frame {i}/{n}')
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    return mp4, total
