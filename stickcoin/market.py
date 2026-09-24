"""Piyasa verisi: CoinGecko (trend, fiyat, logo) + borsa mumları (Binance -> OKX -> KuCoin -> Bybit).

Borsa mumu, CoinGecko fiyatından %5'ten fazla saparsa o borsa reddedilir (aynı sembollü başka coin olabilir).
Hiçbir borsada USDT paritesi bulunamayan coin işlenmez (Bölüm 5 filtresi).
"""
import io
import os
import re
import time

import numpy as np
import requests

from . import CONFIG, ROOT

CG = 'https://api.coingecko.com/api/v3'
LOGOS = ROOT / 'assets' / 'logos'
UA = {'User-Agent': 'stickcoin/1.0'}


def log(m):
    print(f'[market] {m}', flush=True)


def cg(path, **params):
    headers = dict(UA)
    key = (os.environ.get('COINGECKO_API_KEY') or '').strip()
    if key:
        headers['x-cg-demo-api-key'] = key
    for attempt in range(5):
        r = requests.get(CG + path, params=params, headers=headers, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            wait = 15 * (attempt + 1)
            log(f'CoinGecko {r.status_code}, waiting {wait}s')
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f'CoinGecko unavailable: {path}')


def trending_ids():
    return [c['item']['id'] for c in cg('/search/trending').get('coins', [])]


def markets(ids=None, pages=1):
    rows = []
    for page in range(1, pages + 1):
        params = dict(vs_currency='usd', order='market_cap_desc', per_page=250, page=page,
                      price_change_percentage='24h,7d')
        if ids:
            params['ids'] = ','.join(ids)
        rows += cg('/coins/markets', **params)
        if ids:
            break
    return rows


def eligible(m):
    f = CONFIG['filters']
    sym, name = (m.get('symbol') or '').lower(), (m.get('name') or '').lower()
    if sym in f['exclude_symbols']:
        return False
    if any(re.search(rf'\b{re.escape(w)}\b', name) for w in f['exclude_name_words']):
        return False
    if (m.get('market_cap') or 0) < f['min_market_cap'] or (m.get('total_volume') or 0) < f['min_volume_24h']:
        return False
    price, chg = m.get('current_price') or 0, m.get('price_change_percentage_24h') or 0
    if 0.97 <= price <= 1.03 and abs(chg) < 1.5:  # isimden kaçan stablecoin
        return False
    return True


def coin_info(coin_id):
    """Proje bilgisi (CoinGecko): kategoriler, kısa açıklama, çıkış yılı. 'What is it?' formatı ve panolar için."""
    try:
        d = cg(f'/coins/{coin_id}', localization='false', tickers='false', market_data='false',
               community_data='false', developer_data='false', sparkline='false')
    except Exception as e:
        log(f'coin info unavailable for {coin_id}: {e}')
        return {}
    desc = re.sub(r'<[^>]+>', '', (d.get('description') or {}).get('en') or '')
    desc = re.sub(r'\s+', ' ', desc).strip()
    if len(desc) > 900:
        cut = desc[:900]
        desc = cut[:cut.rfind('.') + 1] or cut
    skip = re.compile(r'portfolio|ecosystem|binance|coinbase|bybit|okx|kucoin|kraken|launchpad|launchpool|spotlight|'
                      r'alpha|listing|holdings|made in|index', re.I)
    cats = [c for c in (d.get('categories') or []) if c and not skip.search(c)]
    year = (d.get('genesis_date') or '')[:4]
    return {'categories': cats[:4], 'description': desc, 'launched': int(year) if year.isdigit() else None}


def price_now(coin_id):
    return float(cg('/simple/price', ids=coin_id, vs_currencies='usd')[coin_id]['usd'])


# ------------------------------------------------------------------ mumlar

def _binance(sym, limit):
    r = requests.get('https://data-api.binance.vision/api/v3/klines',
                     params=dict(symbol=f'{sym}USDT', interval='4h', limit=limit), headers=UA, timeout=20)
    r.raise_for_status()
    return [[k[0] / 1000, k[1], k[2], k[3], k[4], k[5]] for k in r.json()]


def _okx(sym, limit):
    r = requests.get('https://www.okx.com/api/v5/market/candles',
                     params=dict(instId=f'{sym}-USDT', bar='4H', limit=min(limit, 300)), headers=UA, timeout=20)
    r.raise_for_status()
    return [[int(k[0]) / 1000, k[1], k[2], k[3], k[4], k[5]] for k in reversed(r.json().get('data', []))]


def _kucoin(sym, limit):
    r = requests.get('https://api.kucoin.com/api/v1/market/candles',
                     params=dict(type='4hour', symbol=f'{sym}-USDT'), headers=UA, timeout=20)
    r.raise_for_status()
    rows = [[int(k[0]), k[1], k[3], k[4], k[2], k[5]] for k in reversed(r.json().get('data') or [])]
    return rows[-limit:]


def _bybit(sym, limit):
    r = requests.get('https://api.bybit.com/v5/market/kline',
                     params=dict(category='spot', symbol=f'{sym}USDT', interval='240', limit=min(limit, 1000)),
                     headers=UA, timeout=20)
    r.raise_for_status()
    return [[int(k[0]) / 1000, k[1], k[2], k[3], k[4], k[5]] for k in reversed(r.json()['result']['list'])]


SOURCES = [('binance', _binance), ('okx', _okx), ('kucoin', _kucoin), ('bybit', _bybit)]


def klines(symbol, ref_price, limit=None):
    """-> (source, ndarray [N,6]: time, open, high, low, close, volume) veya (None, None)."""
    limit = limit or CONFIG['chart']['history_candles']
    sym = symbol.upper()
    for name, fn in SOURCES:
        try:
            rows = fn(sym, limit)
        except Exception as e:
            log(f'{name} {sym}: {type(e).__name__}')
            continue
        if len(rows) < 120:
            continue
        a = np.asarray(rows, dtype=np.float64)
        dev = abs(a[-1, 4] / ref_price - 1) * 100
        if dev > 5:
            log(f'{name} {sym}USDT price {a[-1, 4]} vs CoinGecko {ref_price} ({dev:.1f}% off), rejected')
            continue
        return name, a
    return None, None


# ------------------------------------------------------------------ logo

def logo(coin):
    """CoinGecko görselini assets/logos/<id>.png olarak önbelleğe alır."""
    from PIL import Image
    LOGOS.mkdir(parents=True, exist_ok=True)
    path = LOGOS / f"{coin['id']}.png"
    if path.exists():
        return path
    url = (coin.get('image') or '').replace('/small/', '/large/').replace('/thumb/', '/large/')
    if not url:
        return None
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert('RGBA')
        img.thumbnail((256, 256))
        img.save(path)
        return path
    except Exception as e:
        log(f'logo download failed for {coin["id"]}: {e}')
        return None
