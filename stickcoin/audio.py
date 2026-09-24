"""Ses: karakter sesleri (Kokoro, açık kaynak, CPU), sentezlenmiş SFX ve prosedürel müzik.

SFX ve müzik tamamen kodla üretilir -> lisans kaydı gerekmez, telif riski yok.
"""
import os
import re
from pathlib import Path

import numpy as np

from .cast import CAST

SR = 48000
CACHE = Path(os.environ.get('STICKSTORY_CACHE', Path.home() / '.cache' / 'stickstory')) / 'kokoro'
MODEL_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
MODEL, VOICES = 'kokoro-v1.0.onnx', 'voices-v1.0.bin'
_kokoro = None


def _engine():
    global _kokoro
    if _kokoro is None:
        import requests
        from kokoro_onnx import Kokoro
        CACHE.mkdir(parents=True, exist_ok=True)
        for name in (MODEL, VOICES):
            path = CACHE / name
            if path.exists() and path.stat().st_size > 1_000_000:
                continue
            print(f'[tts] downloading {name}', flush=True)
            with requests.get(MODEL_URL + name, stream=True, timeout=300) as r:
                r.raise_for_status()
                tmp = path.with_suffix('.part')
                with tmp.open('wb') as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.replace(path)
        _kokoro = Kokoro(str(CACHE / MODEL), str(CACHE / VOICES))
    return _kokoro


def resample(x, factor):
    """factor > 1 -> kısalır (perde yükselir)."""
    n = max(1, int(len(x) / factor))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def spoken(text):
    t = re.sub(r'[\U00010000-\U0010ffff]', '', text)  # emoji
    t = t.replace('&', ' and ').replace('%', ' percent')
    return re.sub(r'\s+', ' ', t).strip()


def speak(cid, tokens, emotion='neutral', speed_mul=1.0):
    """tokens: [(ekranda, okunuş)] -> (samples float32 @SR, words [{text,say,start,end}])

    Sayılar ekranda "$182.40", seste "one hundred eighty-two dollars forty" olur; kelime zamanlaması okunuşa göre.
    """
    c = CAST[cid]
    pitch = c['pitch']
    speed = c['speed'] * speed_mul
    if emotion in ('angry', 'excited', 'shock'):
        speed *= 1.06
    elif emotion in ('sad', 'cry'):
        speed *= 0.94
    text = ' '.join(say for _, say in tokens)
    samples, sr = _engine().create(spoken(text), voice=c['voice'], speed=speed / pitch, lang='en-us')
    samples = np.asarray(samples, np.float32)
    # baştaki/sondaki sessizliği kırp
    thr = 0.01 * (np.abs(samples).max() + 1e-6)
    idx = np.where(np.abs(samples) > thr)[0]
    if len(idx):
        samples = samples[max(0, idx[0] - int(0.02 * sr)): idx[-1] + int(0.06 * sr)]
    samples = resample(samples, pitch * sr / SR)
    if emotion in ('angry', 'shock', 'excited'):
        samples = np.tanh(samples * 1.6) / np.tanh(1.6)
    samples = samples / (np.abs(samples).max() + 1e-6) * 0.9
    dur = len(samples) / SR
    weights = [max(1, len(re.sub(r'[^A-Za-z0-9]', '', say))) + 2 * len(say.split()) for _, say in tokens]
    total = sum(weights) or 1
    words, cur = [], 0.0
    for (tok, say), w in zip(tokens, weights):
        d = dur * w / total
        words.append({'text': tok, 'say': say, 'start': cur, 'end': cur + d})
        cur += d
    return samples, words


# ------------------------------------------------------------------ SFX

def _t(d):
    return np.arange(int(d * SR)) / SR


def _env(n, a=0.002, decay=10.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t * decay)


def _noise(n, rng):
    return rng.uniform(-1, 1, n).astype(np.float32)


def _lp(x, k):
    """basit alçak geçiren (hareketli ortalama)."""
    k = max(1, int(k))
    if k == 1:
        return x
    c = np.cumsum(np.pad(np.asarray(x, np.float64), (k // 2, k - k // 2)))
    return ((c[k:] - c[:-k]) / k)[:len(x)].astype(np.float32)


def sfx(name, seed=0):
    rng = np.random.default_rng(seed)
    if name == 'slap':
        n = int(0.25 * SR)
        x = _noise(n, rng) * _env(n, 0.0005, 30) + np.sin(2 * np.pi * 180 * _t(0.25)) * _env(n, 0.001, 25) * 0.6
    elif name == 'whoosh':
        t = _t(0.45)
        x = _noise(len(t), rng)
        x = _lp(x, 6) * np.sin(np.pi * t / 0.45) ** 2
    elif name == 'boing':
        t = _t(0.6)
        f = 220 + 180 * np.exp(-t * 4) * np.sin(2 * np.pi * 9 * t)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.003, 4.5)
    elif name == 'pop':
        t = _t(0.12)
        f = 900 - 5000 * t
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 35)
    elif name == 'thud':
        t = _t(0.4)
        f = 110 * np.exp(-t * 6) + 40
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 9) + _lp(_noise(len(t), rng), 20) * _env(len(t), 0.001, 30)
    elif name == 'door':
        t = _t(0.5)
        x = np.sin(2 * np.pi * np.cumsum(70 + 60 * np.exp(-t * 10)) / SR) * _env(len(t), 0.001, 7) \
            + _lp(_noise(len(t), rng), 4) * _env(len(t), 0.0005, 25) * 0.8
    elif name == 'ding':
        t = _t(1.0)
        x = (np.sin(2 * np.pi * 1320 * t) + 0.5 * np.sin(2 * np.pi * 2640 * t) + 0.3 * np.sin(2 * np.pi * 3960 * t)) \
            * _env(len(t), 0.002, 4) * 0.6
    elif name == 'crash':
        t = _t(1.0)
        x = _noise(len(t), rng) * _env(len(t), 0.001, 4) + _lp(_noise(len(t), rng), 30) * _env(len(t), 0.001, 8)
    elif name == 'rimshot':
        parts = []
        for f, d in ((200, 0.14), (160, 0.14)):
            t = _t(d)
            parts.append(np.sin(2 * np.pi * np.cumsum(f * np.exp(-t * 8)) / SR) * _env(len(t), 0.001, 18))
        t = _t(0.9)
        parts.append(_noise(len(t), rng) * _env(len(t), 0.001, 5) * 0.55 - _lp(_noise(len(t), rng), 3) * 0.2 * _env(len(t), 0.001, 5))
        x = np.concatenate(parts)
    elif name == 'sting':  # "dun dun duuun"
        parts = []
        for f, d in ((146.8, 0.28), (138.6, 0.28), (110, 1.1)):
            t = _t(d)
            w = sum(np.sign(np.sin(2 * np.pi * f * h * t)) / h for h in (1, 2, 3))
            parts.append(_lp(w, 8) * _env(len(t), 0.005, 2.5 if d > 1 else 5))
        x = np.concatenate(parts) * 0.6
    elif name == 'buzz':
        t = _t(0.7)
        x = np.sign(np.sin(2 * np.pi * 95 * t)) * 0.5 * _env(len(t), 0.005, 2)
        x = _lp(x, 6)
    elif name == 'gasp_hit':
        t = _t(0.5)
        x = np.sin(2 * np.pi * np.cumsum(300 + 900 * t) / SR) * _env(len(t), 0.003, 5) * 0.7
    elif name == 'cash':  # yazar kasa "ka-ching": mekanik tık + iki parlak zil
        click = _lp(_noise(int(0.08 * SR), rng), 2) * _env(int(0.08 * SR), 0.0005, 60)
        t = _t(0.9)
        bell = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((2093, 0.6), (2637, 0.5), (4186, 0.25)))
        bell2 = np.concatenate([np.zeros(int(0.09 * SR)), bell[:-int(0.09 * SR)]])
        x = np.concatenate([click, bell * _env(len(t), 0.002, 5) * 0.6 + bell2 * _env(len(t), 0.002, 4)])
    elif name == 'rocket':  # yükselen gürültü + ton
        t = _t(1.3)
        roar = _lp(_noise(len(t), rng), 12) * np.minimum(1, t / 0.15) * np.exp(-np.maximum(0, t - 0.9) * 6)
        tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * t ** 2) / SR) * 0.35 * np.minimum(1, t / 0.2)
        x = roar + tone * np.exp(-np.maximum(0, t - 0.9) * 6)
    elif name == 'cry':  # "waa-waa" inen trombon
        parts = []
        for f0, d in ((392, 0.32), (370, 0.32), (349, 0.32), (330, 0.9)):
            t = _t(d)
            f = f0 * (1 + 0.012 * np.sin(2 * np.pi * 6 * t)) * (1 - 0.06 * t / d)
            w = sum(np.sin(2 * np.pi * np.cumsum(f * h) / SR) / h for h in (1, 2, 3, 4))
            parts.append(_lp(w, 3) * np.minimum(1, t / 0.03) * np.exp(-t * (1.2 if d > 0.5 else 3)))
        x = np.concatenate(parts)
    else:
        x = np.zeros(10)
    x = np.asarray(x, np.float32)
    return x / (np.abs(x).max() + 1e-6) * 0.8


# ------------------------------------------------------------------ müzik

PROGS = [
    [0, 5, 3, 4],  # I vi IV V
    [0, 3, 4, 3],
    [0, 4, 5, 3],
    [5, 3, 0, 4],
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]


def _pluck(f, d, bright=0.5):
    t = _t(d)
    w = np.sin(2 * np.pi * f * t) + bright * 0.5 * np.sin(4 * np.pi * f * t) + bright * 0.25 * np.sin(6 * np.pi * f * t)
    return w * _env(len(t), 0.003, 7)


MINOR = [0, 2, 3, 5, 7, 8, 10]


def music(duration, seed=0, mood='bullish'):
    """Hafif, zıplayan alt yapı: pizzicato akorları + bas + tık tık. Düşüşte minör gam."""
    rng = np.random.default_rng(seed)
    scale = MAJOR if mood == 'bullish' else MINOR
    bpm = rng.choice([104, 112, 120, 126])
    beat = 60 / bpm
    root = 48 + int(rng.integers(0, 7))  # C3..F#3
    prog = PROGS[int(rng.integers(len(PROGS)))]
    bright = float(rng.uniform(0.3, 0.9))
    bars = 4
    loop = np.zeros(int(bars * 4 * beat * SR) + SR)

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    pattern = rng.choice([[0, 2, 1, 2], [0, 1, 2, 1], [0, 2, 0, 1]])
    for bar in range(bars):
        deg = prog[bar % 4]
        chord = [root + 12 + scale[(deg + k) % 7] + 12 * ((deg + k) // 7) for k in (0, 2, 4)]
        for b in range(4):
            t0 = int((bar * 4 + b) * beat * SR)
            bass = _pluck(hz(root + scale[deg % 7] - 12 + (7 if b % 2 else 0)), beat * 0.9, 0.2) * 0.55
            loop[t0:t0 + len(bass)] += bass
            for half in (0, 1):
                n = chord[pattern[(b * 2 + half) % 4]] + (12 if half else 0)
                p = _pluck(hz(n), beat * 0.6, bright) * 0.28
                s = t0 + int(half * beat / 2 * SR)
                loop[s:s + len(p)] += p
            tick = _noise(int(0.03 * SR), rng) * _env(int(0.03 * SR), 0.0005, 120) * 0.12
            s = t0 + int(beat / 2 * SR)
            loop[s:s + len(tick)] += tick
    loop = loop[:int(bars * 4 * beat * SR)]
    reps = int(np.ceil(duration * SR / len(loop))) + 1
    out = np.tile(loop, reps)[:int(duration * SR)]
    return (out / (np.abs(out).max() + 1e-6)).astype(np.float32)


def mix(total, voices, effects, music_track, speech_mask):
    """voices/effects: [(start_sec, samples, gain)] -> stereo float32."""
    n = int(total * SR) + 1
    v = np.zeros(n, np.float32)
    for start, s, g in voices + effects:
        i = int(start * SR)
        seg = s[: max(0, n - i)]
        v[i:i + len(seg)] += seg * g
    # ducking: konuşma varken müzik kısılır (yumuşak geçiş)
    duck = np.interp(np.arange(n) / SR, speech_mask[0], speech_mask[1]).astype(np.float32)
    duck = _lp(duck, int(0.15 * SR))
    m = music_track[:n]
    m = np.pad(m, (0, n - len(m)))
    out = v + m * (0.16 - 0.09 * duck)
    fade = int(0.4 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = np.tanh(out * 1.1) * 0.92
    return np.stack([out, out], axis=1)
