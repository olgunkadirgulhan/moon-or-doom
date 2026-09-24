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
        if v['coin'] != coin_id:
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


def build(m, reason, vid, mover_rank=None, trending_rank=None):
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
        'chart': {'interval': '4h', 'source': source, 'candles': a[-show:, :5].round(10).tolist()},
        'created_utc': now().strftime('%Y-%m-%d %H:%M'),
    }
    for k in ('price', 'resistance_1', 'resistance_2', 'support_1', 'support_2', 'ema_50', 'ema_200'):
        if data[k] is not None and not np.isfinite(data[k]):
            data[k] = None
    return data


def pick(kind, hist, vid, exclude=()):
    """kind: 'gainer' | 'loser'. Sıradaki (48 saat kuralına takılmayan, grafiği olan) en uç hareketli."""
    lists, trend = movers()
    for rank, m in enumerate(lists[kind][:40], 1):
        if m['id'] in exclude or blocked(m['id'], m['current_price'], hist):
            continue
        data = build(m, f'top_{kind}_24h', vid, rank, trend.get(m['id']))
        if data:
            log(f"{kind}: {data['coin']['symbol']} (#{rank}, {data['change_24h_pct']:+.1f}%, via {data['chart']['source']})")
            return data
    raise RuntimeError(f'no eligible {kind} found')


def load_hist(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'videos': []}
