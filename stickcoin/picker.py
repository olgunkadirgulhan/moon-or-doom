"""Coin seçimi (Bölüm 2 + 5) ve senaryo girdisi olan veri JSON'u (Bölüm 7)."""
import json
from datetime import datetime, timedelta, timezone

import numpy as np

from . import CONFIG, ROOT, levels, market

MAJORS = ['bitcoin', 'ethereum']


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


def majors_due(hist):
    days = CONFIG['repeat']['majors_every_days']
    today = now().strftime('%Y-%m-%d')
    if any(v['coin'] in MAJORS and v['date'].startswith(today) for v in hist.get('videos', [])):
        return []  # günde en fazla bir major
    due = []
    for cid in MAJORS:
        last = [parse(v['date']) for v in hist.get('videos', []) if v['coin'] == cid]
        if not last or now() - max(last) > timedelta(days=days):
            due.append(cid)
    return due


def candidates(slot, hist):
    trend = market.trending_ids()
    trend_rows = {m['id']: m for m in market.markets(trend)} if trend else {}
    top = [m for m in market.markets(pages=1) if market.eligible(m)]
    by_id = {m['id']: m for m in top}
    by_id.update(trend_rows)
    trending = [(by_id[i], f'coingecko_trending_rank_{k + 1}') for k, i in enumerate(trend)
                if i in trend_rows and market.eligible(trend_rows[i])]
    ranked = sorted(top, key=lambda m: m.get('price_change_percentage_24h') or 0)
    gainers = [(m, 'top_gainer_24h') for m in reversed(ranked) if (m.get('price_change_percentage_24h') or 0) > 3]
    losers = [(m, 'top_loser_24h') for m in ranked if (m.get('price_change_percentage_24h') or 0) < -3]
    majors = [(by_id[c], 'weekly_major') for c in majors_due(hist) if c in by_id]
    if slot == 1:
        order = trending + gainers + losers
    elif slot == 2:
        order = majors + trending + gainers + losers
    else:
        strong_losers = [x for x in losers if x[0]['price_change_percentage_24h'] <= -5]
        order = strong_losers + trending + losers + gainers
    seen, out = set(), []
    for m, why in order:
        if m['id'] not in seen:
            seen.add(m['id']); out.append((m, why))
    return out


def build(m, reason, vid):
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
    rank = int(reason.rsplit('_', 1)[1]) if reason.startswith('coingecko_trending_rank_') else None
    data = {
        'id': vid,
        'coin': {'id': m['id'], 'symbol': m['symbol'].upper(), 'name': m['name'],
                 'logo': str(market.logo(m) or ''), 'market_cap_rank': m.get('market_cap_rank')},
        'reason_trending': reason,
        'trending_rank': rank,
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


def pick(slot, hist, vid, exclude=()):
    for m, why in candidates(slot, hist):
        if m['id'] in exclude or blocked(m['id'], m['current_price'], hist):
            continue
        data = build(m, why, vid)
        if data:
            log(f"picked {data['coin']['symbol']} ({why}, {data['change_24h_pct']:+.1f}%, via {data['chart']['source']})")
            return data
    raise RuntimeError('no eligible coin found')


def load_hist(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'videos': []}
