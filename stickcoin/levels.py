"""Destek/direnç + RSI/EMA/hacim (Bölüm 6). Tüm sayılar buradan gelir; LLM sayı üretmez."""
import math

import numpy as np

from . import CONFIG


def round_level(p):
    """1 doların üstü 2 ondalık, altı 4 anlamlı basamak."""
    if p is None:
        return None
    if p >= 1:
        return round(float(p), 2)
    digits = 3 - int(math.floor(math.log10(abs(p))))
    return round(float(p), digits)


def swing_points(high, low, window=5):
    """Yerel tepe ve dipler."""
    highs, lows = [], []
    for i in range(window, len(high) - window):
        if high[i] == high[i - window:i + window + 1].max():
            highs.append(high[i])
        if low[i] == low[i - window:i + window + 1].min():
            lows.append(low[i])
    return highs, lows


def cluster_levels(levels, tolerance_pct=1.0):
    """Birbirine %1'den yakın seviyeleri tek seviyede birleştirir; dokunuş sayısını tutar."""
    clusters = []
    for lvl in sorted(levels):
        if clusters and abs(lvl - clusters[-1]['price']) / clusters[-1]['price'] * 100 < tolerance_pct:
            c = clusters[-1]
            c['touches'] += 1
            c['price'] = (c['price'] * (c['touches'] - 1) + lvl) / c['touches']
        else:
            clusters.append({'price': float(lvl), 'touches': 1})
    return clusters


def support_resistance(a):
    """a: [N,6] time, open, high, low, close, volume."""
    cfg = CONFIG['chart']
    high, low, close = a[:, 2], a[:, 3], a[:, 4]
    price = float(close[-1])
    highs, lows = swing_points(high, low)
    levels = cluster_levels(highs + lows)

    def usable(l):
        d = abs(l['price'] / price - 1) * 100
        return cfg['level_min_pct'] <= d <= cfg['level_max_pct']

    levels = [l for l in levels if usable(l)]
    above = [l for l in levels if l['price'] > price]
    below = [l for l in levels if l['price'] < price]
    # güç: dokunuş sayısı, eşitlikte fiyata yakınlık; en güçlü 3'ün en yakını ana seviye
    res = sorted(sorted(above, key=lambda l: (-l['touches'], l['price'] - price))[:3], key=lambda l: l['price'])
    sup = sorted(sorted(below, key=lambda l: (-l['touches'], price - l['price']))[:3], key=lambda l: -l['price'])
    r1 = res[0]['price'] if res else None
    s1 = sup[0]['price'] if sup else None
    # ana seviye yoksa pencerenin tepe/dibi (kullanılabilir aralıktaysa)
    if r1 is None and usable({'price': float(high.max())}) and high.max() > price:
        r1 = float(high.max())
    if s1 is None and usable({'price': float(low.min())}) and low.min() < price:
        s1 = float(low.min())
    # ikincil: ana seviyenin ötesindeki bir sonraki seviye
    r2 = next((l['price'] for l in res[1:]), None) or next((l['price'] for l in sorted(above, key=lambda l: l['price'])
                                                          if r1 and l['price'] > r1 * 1.01), None)
    s2 = next((l['price'] for l in sup[1:]), None) or next((l['price'] for l in sorted(below, key=lambda l: -l['price'])
                                                          if s1 and l['price'] < s1 * 0.99), None)
    return {
        'price': round_level(price),
        'resistance_1': round_level(r1),
        'resistance_2': round_level(r2),
        'support_1': round_level(s1),
        'support_2': round_level(s2),
    }


def ema(x, span):
    k = 2 / (span + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(close, n=14):
    """Wilder RSI (TradingView ile aynı yöntem)."""
    d = np.diff(close)
    gain, loss = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = gain[:n].mean(), loss[:n].mean()
    for g, l in zip(gain[n:], loss[n:]):
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def extras(a):
    close, vol = a[:, 4], a[:, 5]
    base = vol[-60:-6].mean() if len(vol) >= 60 else vol[:-6].mean()
    return {
        'rsi_14': round(float(rsi(close)), 1),
        'ema_50': round_level(float(ema(close, 50)[-1])),
        'ema_200': round_level(float(ema(close, 200)[-1])),
        'volume_vs_avg': round(float(vol[-6:].sum() / (base * 6)), 1) if base > 0 else None,
        'change_7d_pct': round(float((close[-1] / close[-43] - 1) * 100), 1) if len(close) > 43 else None,
    }
