"""Coin seçimi: her çalıştırmada günün en çok yükseleni + en çok düşeni (Bölüm 5 filtresi, 48 saat kuralı)
ve senaryo girdisi olan veri JSON'u (Bölüm 7)."""
import json
from datetime import datetime, timedelta, timezone

import numpy as np

from . import CONFIG, levels, market

KINDS = ('gainer', 'loser')


def log(m):
    print(f'[picker] {m}', flush=True)


def now():
    return datetime.now(timezone.utc)


def parse(ts):
    return datetime.strptime(ts, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)


def blocked(coin_id, price, hist):
    """48 saat kuralı: son videodan beri %15'ten fazla hareket yoksa tekrar işlenmez."""
    rep = CONFIG['repeat']
    for v in reversed(hist.get('videos', [])):
        if v.get('coin') != coin_id:
            continue
        if now() - parse(v['date']) > timedelta(hours=rep['hours']):
            return False
        return abs(price / v['price'] - 1) * 100 <= rep['move_override_pct']
    return False


_movers = None


def movers():
    """-> {'gainer': [market satırı...], 'loser': [...]}, trend sıraları (çalıştırma başına bir kez çekilir)."""
    global _movers
    if _movers is None:
        try:
            trend = market.trending_ids()
        except Exception as e:
            log(f'trending unavailable: {e}'); trend = []
        top = [m for m in market.markets(pages=CONFIG['universe_pages']) if market.eligible(m)]
        ranked = sorted(top, key=lambda m: m.get('price_change_percentage_24h') or 0)
        _movers = ({'gainer': list(reversed(ranked)), 'loser': ranked},
                   {cid: k + 1 for k, cid in enumerate(trend)})
    return _movers


def build(m, reason, vid, mover_rank=None, trending_rank=None, info=True):
    source, a = market.klines(m['symbol'], m['current_price'])
    if a is None:
        log(f"{m['symbol'].upper()}: no USDT pair on a major exchange, skipped")
        return None
    lv = levels.support_resistance(a)
    if lv['resistance_1'] is None or lv['support_1'] is None:
        log(f"{m['symbol'].upper()}: no usable support/resistance, skipped")
        return None
    ex = levels.extras(a)
    show = CONFIG['chart']['show_candles']
    chg = float(m.get('price_change_percentage_24h') or 0)
    data = {
        'id': vid,
        'coin': {'id': m['id'], 'symbol': m['symbol'].upper(), 'name': m['name'],
                 'logo': str(market.logo(m) or ''), 'market_cap_rank': m.get('market_cap_rank')},
        'reason_trending': reason,
        'mover_rank': mover_rank,
        'trending_rank': trending_rank,
        'change_24h_pct': round(chg, 1),
        'coingecko_price': m['current_price'],
        'volume_24h_usd': m.get('total_volume'),
        'market_cap_usd': m.get('market_cap'),
        **lv, **ex,
        'mood': 'bullish' if chg >= 0 else 'bearish',
        'sidekick': 'moon_max' if chg >= 0 else 'bear_betty',
        'chart': {'interval': '4h', 'source': source, 'candles': a[-show:, :6].round(10).tolist()},
        'info': market.coin_info(m['id']) if info else {},
        'created_utc': now().strftime('%Y-%m-%d %H:%M'),
    }
    c7 = m.get('price_change_percentage_7d_in_currency')
    if c7 is not None:
        data['change_7d_pct'] = round(float(c7), 1)
    for k in ('price', 'resistance_1', 'resistance_2', 'support_1', 'support_2', 'ema_50', 'ema_200'):
        if data[k] is not None and not np.isfinite(data[k]):
            data[k] = None
    return data


_sibling = None


def sibling_titles():
    global _sibling
    if _sibling is None:
        _sibling = market.sibling_titles()
        log(f'{len(_sibling)} recent sibling-channel uploads checked')
    return _sibling


def pick(kind, hist, vid, exclude=()):
    """kind: 'gainer' | 'loser'. Sıradaki (48 saat kuralına ve kardeş kanala takılmayan, grafiği olan) en uç hareketli."""
    lists, trend = movers()
    for rank, m in enumerate(lists[kind][:40], 1):
        if m['id'] in exclude or blocked(m['id'], m['current_price'], hist):
            continue
        if market.mentioned(m, sibling_titles()):
            log(f"{m['symbol'].upper()}: covered by a sibling channel in the last 36h, skipped")
            continue
        data = build(m, f'top_{kind}_24h', vid, rank, trend.get(m['id']))
        if data:
            log(f"{kind}: {data['coin']['symbol']} (#{rank}, {data['change_24h_pct']:+.1f}%, via {data['chart']['source']})")
            return data
    raise RuntimeError(f'no eligible {kind} found')


def pick_long(kind, vid, hist=None):
    """Uzun videolar:
    explained  trend olan 3 proje (açıklaması olan, son 30 günde anlatılmamış, kardeş kanalda son 36 saatte yok)
    school     kavram örnekleri: en büyük coin + günün en çok yükseleni + en çok düşeni
    weekly     haftanın en çok yükselen 3 + düşen 3 (7g)      majors  piyasa değeri ilk 5
    """
    lists, trend = movers()
    out = []
    if kind == 'explained':
        since = now() - timedelta(days=30)
        done = {c for v in (hist or {}).get('videos', []) if v.get('kind') == 'explained' and parse(v['date']) >= since
                for c in v.get('coins', [])}
        pool = sorted([m for m in lists['gainer'] if m['id'] in trend], key=lambda m: trend[m['id']]) + \
            lists['gainer'][:15] + lists['loser'][:15]
        seen = set()
        for m in pool:
            if len(out) == 5:
                break
            if m['id'] in seen or m['id'] in done or market.mentioned(m, sibling_titles()):
                continue
            seen.add(m['id'])
            d = build(m, 'trending' if m['id'] in trend else 'mover', f'{vid}_{len(out) + 1}', len(out) + 1,
                      trend.get(m['id']))
            if d and len((d.get('info') or {}).get('description') or '') >= 120:
                out.append(d)
        return out
    if kind == 'school':
        big = sorted(lists['gainer'], key=lambda m: m.get('market_cap_rank') or 10 ** 6)
        mixed = [m for pair in zip(lists['gainer'][:10], lists['loser'][:10]) for m in pair]
        for m in [big[0]] + mixed:
            if len(out) == 4:
                break
            if any(d['coin']['id'] == m['id'] for d in out):
                continue
            d = build(m, 'example', f'{vid}_{len(out) + 1}', len(out) + 1)
            if d:
                out.append(d)
        return out
    if kind == 'majors':
        rows = sorted(lists['gainer'], key=lambda m: m.get('market_cap_rank') or 10 ** 6)
        for m in rows:
            if len(out) == 5:
                break
            d = build(m, 'major', f'{vid}_{len(out) + 1}', len(out) + 1)
            if d:
                out.append(d)
        return out
    rows = [m for m in lists['gainer'] if m.get('price_change_percentage_7d_in_currency') is not None]
    by7 = sorted(rows, key=lambda m: m['price_change_percentage_7d_in_currency'])
    for side, seq in (('gainer', list(reversed(by7))), ('loser', by7)):
        got = 0
        for m in seq[:30]:
            if got == 3:
                break
            if any(d['coin']['id'] == m['id'] for d in out):
                continue
            d = build(m, f'week_{side}', f'{vid}_{len(out) + 1}', got + 1)
            if d:
                chg7 = d.get('change_7d_pct') or 0
                d['mood'] = 'bullish' if chg7 >= 0 else 'bearish'
                d['sidekick'] = 'moon_max' if chg7 >= 0 else 'bear_betty'
                out.append(d); got += 1
    return out


def load_hist(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'videos': []}
