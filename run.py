"""Çöp Adam Kripto hattı. Bir çalıştırma = 2 video: günün en çok yükseleni + en çok düşeni, arada 5 dk (Bölüm 10).

    coin seçimi -> mumlar + seviyeler -> senaryo (Gemini + doğrulama) -> ses + animasyon -> tazelik kontrolü -> YouTube

Kullanım
  python run.py                      # yükselen + düşen (yükleme secrets varsa)
  python run.py --no-upload          # sadece render: output/<id>/video.mp4
  python run.py --only loser --no-upload
  python run.py --coin solana --no-upload
  python run.py --data output/<id>/data.json --no-upload   # aynı veriyle yeniden render

Env
  GEMINI_API_KEY      senaryo (yoksa kural tabanlı şablon)
  COINGECKO_API_KEY   isteğe bağlı (demo key; rate limit rahatlar)
  YT_PRIVACY          public | private | unlisted | off  (varsayılan: YT secrets varsa private)
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, YT_CHANNEL_ID
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   isteğe bağlı bildirim
"""
import argparse
import json
import os
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import notify  # noqa: E402
from stickcoin import CONFIG, market, picker, render, script, words  # noqa: E402

HIST = HERE / 'history.json'
OUT = HERE / 'output'


def log(msg):
    print(f'[run] {msg}', flush=True)


def gh_annotation(level, msg):
    print(f'::{level}::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'[run] {level.upper()}: {msg}', flush=True)
    if level in ('error', 'warning'):
        notify.message(f'⚠️ StickCoin {level}: {msg}')


def today_count(hist):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return sum(1 for v in hist.get('videos', []) if v['date'].startswith(today))


def privacy_mode(no_upload):
    import upload
    if no_upload:
        return 'off'
    if not upload.configured():
        gh_annotation('warning', 'YouTube secrets missing: render only. Run auth_setup.py to connect the channel.')
        return 'off'
    mode = (os.environ.get('YT_PRIVACY') or '').strip().lower()
    return mode if mode in ('public', 'private', 'unlisted', 'off') else 'private'


def metadata(data, rnd):
    """Bölüm 11: başlık şablonları + sabit açıklama alt kısmı."""
    sym = data['coin']['symbol']
    chg = data['change_24h_pct']
    p = words.price_text
    titles = [f"{sym} {'+' if chg >= 0 else '-'}{abs(chg):.1f}% today — key levels to watch 📊",
              f"Is {sym} about to break {p(data['resistance_1'])}? 👀",
              f"{sym} support at {p(data['support_1'])} — hold or fold? 😬"]
    if data.get('mover_rank') == 1 and data['reason_trending'] == 'top_gainer_24h':
        titles.append(f"{sym} is today's top gainer (+{chg:.1f}%) — what's next? 🚀")
    if data.get('mover_rank') == 1 and data['reason_trending'] == 'top_loser_24h' and chg < 0:
        titles.append(f"{sym} is today's biggest loser ({chg:.1f}%) — where's support? 📉")
    title = rnd.choice(titles)
    lv = [f"🔴 Resistance: {p(data['resistance_1'])}" +
          (f" (next: {p(data['resistance_2'])})" if data.get('resistance_2') else ''),
          f"🟢 Support: {p(data['support_1'])}" + (f" (next: {p(data['support_2'])})" if data.get('support_2') else '')]
    if data.get('rsi_14') is not None:
        lv.append(f"RSI (14, 4H): {data['rsi_14']:.0f}")
    desc = (f"{data['coin']['name']} ({sym}) {'+' if chg >= 0 else '-'}{abs(chg):.1f}% in 24h at {p(data['price'])}. "
            f"Chart Charlie walks through the levels that matter.\n\n" + '\n'.join(lv) + '\n\n'
            'Levels calculated from 4H chart data. Educational content only — not financial advice.\n'
            'Crypto is highly volatile; do your own research.\n\n'
            "Moon or Doom: today's top gainer & top loser, 3x a day. Subscribe so you never miss the levels.\n"
            f"#crypto #{sym.lower()} #MoonOrDoom #shorts")
    tags = ['crypto', data['coin']['name'], sym, f'{sym} price', f"{data['coin']['name']} price prediction",
            'crypto analysis', 'technical analysis', 'support and resistance', 'altcoins', 'crypto news',
            'crypto shorts', 'animation', 'stick figure']
    return title, desc, tags


def produce(kind, hist, vid, args, exclude=()):
    if args.data:
        data = json.loads(Path(args.data).read_text(encoding='utf-8'))
    elif args.coin:
        rows = market.markets([args.coin])
        if not rows:
            raise SystemExit(f'unknown CoinGecko id: {args.coin}')
        data = picker.build(rows[0], 'manual', vid)
        if not data:
            raise SystemExit(f'{args.coin}: no usable chart data')
    else:
        data = picker.pick(kind, hist, vid, exclude)
    out = OUT / vid
    out.mkdir(parents=True, exist_ok=True)
    (out / 'data.json').write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    sc = script.make_script(data, hist, seed=vid)
    sc['id'] = vid
    (out / 'script.json').write_text(json.dumps(sc, indent=2, ensure_ascii=False), encoding='utf-8')
    for L in sc['lines']:
        log(f"  {L['char']:>10} [{L['chart_action']}] {L['display']}")
    mp4, dur = render.render(sc, data, out, preview_png=out / 'thumb.png')
    log(f'rendered {mp4} ({dur:.1f}s, script: {sc["source"]})')
    return data, sc, mp4


def fresh(data):
    """Bölüm 10: render sonrası fiyat %3'ten fazla oynadıysa video iptal."""
    try:
        now = market.price_now(data['coin']['id'])
    except Exception as e:
        log(f'freshness check skipped: {e}'); return True
    move = abs(now / data['coingecko_price'] - 1) * 100
    log(f'freshness: {data["coingecko_price"]} -> {now} ({move:.2f}%)')
    return move <= CONFIG['freshness']['max_move_pct']


def make_one(kind, hist, args, stamp, exclude):
    for attempt in range(2):
        vid = f'crypto_{stamp}_{kind}' + (f'_r{attempt}' if attempt else '')
        data, sc, mp4 = produce(kind, hist, vid, args, exclude)
        if args.data or args.coin or fresh(data):
            return data, sc, mp4
        gh_annotation('warning', f"{data['coin']['symbol']} moved more than {CONFIG['freshness']['max_move_pct']}% "
                                 'since the data was pulled, rebuilding with fresh data')
    raise RuntimeError('price still moving too fast after rebuild')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-upload', action='store_true')
    ap.add_argument('--only', choices=picker.KINDS, help='sadece yükselen ya da sadece düşen')
    ap.add_argument('--coin', help='CoinGecko id (seçimi atla, tek video)')
    ap.add_argument('--data', help='hazır data.json ile render (tek video)')
    args = ap.parse_args()
    import upload

    mode = privacy_mode(args.no_upload)
    hist = picker.load_hist(HIST)
    kinds = ['manual'] if args.coin or args.data else [args.only] if args.only else list(picker.KINDS)
    log(f"videos: {', '.join(kinds)} | upload mode: {mode}")
    if mode != 'off':
        left = CONFIG['daily_videos'] - today_count(hist)
        if left <= 0:
            log(f"daily cap of {CONFIG['daily_videos']} reached, nothing to do"); return
        kinds = kinds[:left]
        try:
            log(f'channel check ok: {upload.check_channel()}')
        except Exception as e:
            gh_annotation('error', f'channel check failed, nothing uploaded: {e}'); raise SystemExit(1)

    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')
    gap = CONFIG['pair_gap_minutes'] * 60
    failed, last_upload, used = False, None, []
    for kind in kinds:
        try:
            data, sc, mp4 = make_one(kind, hist, args, stamp, used)
        except SystemExit:
            raise
        except Exception as e:
            traceback.print_exc(); gh_annotation('error', f'{kind} video failed: {e}'); failed = True; continue
        used.append(data['coin']['id'])
        title, desc, tags = metadata(data, random.Random(data['id']))
        (OUT / data['id'] / 'meta.json').write_text(json.dumps({'title': title, 'description': desc, 'tags': tags},
                                                               indent=2, ensure_ascii=False), encoding='utf-8')
        log(f'title: {title}')
        if mode == 'off':
            log('upload skipped (mode off)'); continue
        if last_upload is not None:  # aynı çalıştırmadaki iki video arası 5 dk
            wait = gap - (time.time() - last_upload)
            if wait > 0:
                log(f'waiting {wait / 60:.1f} min before the next upload'); time.sleep(wait)
        try:
            video_id = upload.upload(mp4, title, desc, tags, mode, category='27')
        except upload.QuotaError:
            gh_annotation('warning', 'YouTube quota reached, remaining videos skipped.'); break
        except Exception as e:
            traceback.print_exc(); gh_annotation('error', f'upload failed: {e}'); failed = True; continue
        last_upload = time.time()
        url = f'https://youtube.com/shorts/{video_id}'
        log(f'uploaded {url} ({mode})')
        hist.setdefault('videos', []).append({
            'id': data['id'], 'coin': data['coin']['id'], 'symbol': data['coin']['symbol'],
            'price': data['coingecko_price'], 'change_24h_pct': data['change_24h_pct'], 'kind': kind,
            'hook': sc['hook'], 'punch': sc['punch'], 'script': sc['source'], 'video_id': video_id, 'privacy': mode,
            'title': title, 'date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})
        hist['videos'] = hist['videos'][-300:]
        HIST.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding='utf-8')
        pls = json.loads((HERE / 'playlists.json').read_text(encoding='utf-8')) if (HERE / 'playlists.json').exists() else {}
        if kind in pls:
            try:
                upload.add_to_playlist(pls[kind], video_id); log(f'added to playlist {kind}')
            except Exception as e:
                log(f'playlist add skipped: {str(e)[:160]}')
        notify.video(mp4, f'✅ {title}\n{url} ({mode})')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()


