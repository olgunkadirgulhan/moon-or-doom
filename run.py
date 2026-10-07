"""Moon or Doom hattı.

Shorts (günde 2 çalıştırma x 2 video = 4): günün en çok yükseleni + en çok düşeni, arada 5 dk. Her videonun formatı
farklı (levels / what_is / school / skit) — YouTube'un "tekrarlayan içerik" riskine karşı.
Uzun video (haftada 2, 16:9): Çarşamba 'majors' (piyasa değeri ilk 5), Pazar 'weekly' (haftanın 3+3 hareketlisi).

    coin seçimi -> mumlar + seviyeler -> senaryo (Gemini + doğrulama) -> ses + animasyon -> tazelik kontrolü -> YouTube

Kullanım
  python run.py                          # Shorts: yükselen + düşen (yükleme secrets varsa)
  python run.py --no-upload              # sadece render: output/<id>/video.mp4
  python run.py --only loser --format school --no-upload
  python run.py --coin solana --no-upload
  python run.py --long weekly --no-upload
  python run.py --long majors --no-upload

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
import re
import shutil
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import notify  # noqa: E402
from stickcoin import CONFIG, formats, market, picker, render, script, thumbs, words  # noqa: E402
from stickcoin.formats import CONCEPTS, SHORT_FORMATS  # noqa: E402

HIST = HERE / 'history.json'
OUT = HERE / 'output'
SHORT_KINDS = ('gainer', 'loser', 'manual')


def log(msg):
    print(f'[run] {msg}', flush=True)


def gh_annotation(level, msg):
    print(f'::{level}::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'[run] {level.upper()}: {msg}', flush=True)
    if level in ('error', 'warning'):
        notify.message(f'⚠️ Moon or Doom {level}: {msg}')


def today_count(hist):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return sum(1 for v in hist.get('videos', []) if v['date'].startswith(today) and v.get('kind') in SHORT_KINDS)


def privacy_mode(no_upload):
    import upload
    if no_upload:
        return 'off'
    if not upload.configured():
        gh_annotation('warning', 'YouTube secrets missing: render only. Run auth_setup.py to connect the channel.')
        return 'off'
    mode = (os.environ.get('YT_PRIVACY') or '').strip().lower()
    return mode if mode in ('public', 'private', 'unlisted', 'off') else 'private'


def signed(x):
    return f"{'+' if x >= 0 else '-'}{abs(x):.1f}%"


# ------------------------------------------------------------------ başlık / açıklama

def levels_block(data):
    p = words.price_text
    lv = [f"🔴 Resistance: {p(data['resistance_1'])}" +
          (f" (next: {p(data['resistance_2'])})" if data.get('resistance_2') else ''),
          f"🟢 Support: {p(data['support_1'])}" + (f" (next: {p(data['support_2'])})" if data.get('support_2') else '')]
    if data.get('rsi_14') is not None:
        lv.append(f"RSI (14, 4H): {data['rsi_14']:.0f}")
    return lv


FOOTER = ('Levels calculated from 4H chart data. Educational entertainment only — not financial advice.\n'
          'Crypto is highly volatile; do your own research.\n\n')


def title_shape(t):
    """Başlığın kalıbı (sembol ve sayılar atılır): aynı kalıp üst üste = tekrarlayan içerik sinyali."""
    return re.sub(r'[A-Z]{2,6}|[\d.,$+%\-−]+', 'X', t or '').strip()


def metadata(data, sc, rnd, recent_titles=()):
    sym, name = data['coin']['symbol'], data['coin']['name']
    chg = data['change_24h_pct']
    p = words.price_text
    fmt = sc['format']
    top = data.get('mover_rank') == 1
    role = ("today's top gainer" if data['reason_trending'] == 'top_gainer_24h' else
            "today's biggest loser" if chg < 0 else "today's weakest big coin") if top else \
        ('one of today\'s top gainers' if chg >= 0 else 'one of today\'s biggest losers')
    if fmt == 'what_is':
        titles = [f"What is {name}? {sym} is {role} ({signed(chg)}) 🤔", f"{name} ({sym}) {signed(chg)} today — what even is it? 🤔"]
        intro = f"What is {name}, and why is it {role}? Chart Charlie explains the project, then the levels."
    elif fmt == 'school':
        ct = CONCEPTS[sc['concept']][1]
        titles = [f"{ct} Explained with {sym} ({signed(chg)} today) 📚", f"Chart School: {ct} — {sym} example 📚"]
        intro = f"Chart School: {ct.lower()} explained in under a minute, using {name} ({signed(chg)} today) as the example."
    elif fmt == 'skit':
        verb = 'pumps' if chg >= 0 else 'dumps'
        who = 'Moon Max' if chg >= 0 else 'Bear Betty'
        titles = [f"When {sym} {verb} {abs(chg):.1f}% in a day 😂", f"{who} vs {sym} {signed(chg)} 😂"]
        intro = f"{who} reacts to {name} {signed(chg)} today — and Chart Charlie brings the chart."
    else:
        titles = [f"{sym} {signed(chg)} today — support & resistance levels 📊",
                  f"{sym} key levels: resistance {p(data['resistance_1'])}, support {p(data['support_1'])} 📊"]
        if top:
            titles.append(f"{sym} is {role} ({signed(chg)}) — the levels on the chart 📈")
        intro = f"{name} ({sym}) is {role} at {p(data['price'])}. Chart Charlie maps the support and resistance."
    # karakter tepkili başlıklar (Dex & Friends'te en iyi çalışan stil: duygu + emoji)
    if chg >= 0:
        titles += [f"Moon Max lost it when {sym} went {signed(chg)} 😭", f"{sym} {signed(chg)} today and Moon Max is NOT okay 🚀",
                   f"{name} pumped {signed(chg)}. Moon Max has questions 🤔", f"{sym} {signed(chg)} in 24h: where's the next wall? 🧱",
                   f"Moon Max vs Bear Betty: {sym} {signed(chg)} 🥊", f"{sym} just ran {signed(chg)}. Chart Charlie checks the levels 📈"]
    else:
        titles += [f"Bear Betty saw {sym} {signed(chg)} and smiled 😈", f"{sym} {signed(chg)}… Bear Betty called it 💀",
                   f"{name} dropped {abs(chg):.1f}%. Where's the floor? 📉", f"{sym} {signed(chg)} in 24h: the support to watch 👀",
                   f"Moon Max is coping hard: {sym} {signed(chg)} 🫠", f"{sym} {signed(chg)}. Chart Charlie draws the line 📏"]
    # son 12 videoda kullanılmış başlık kalıbı seçilmez
    used = {title_shape(t) for t in recent_titles}
    titles = [t for t in titles if title_shape(t) not in used] or titles
    desc = (intro + '\n\n' + '\n'.join(levels_block(data)) + '\n\n' + FOOTER +
            "Moon or Doom: today's top gainer & top loser, every day. Subscribe so you never miss the levels.\n"
            f"#crypto #{sym.lower()} #MoonOrDoom #shorts")
    extra = {'what_is': [f'what is {name}', f'{name} explained'], 'school': [CONCEPTS.get(sc.get('concept'), ('', 'chart school'))[1].lower(), 'crypto for beginners', 'learn trading'],
             'skit': ['crypto memes', 'crypto funny'], 'levels': ['support and resistance', 'key levels']}[fmt]
    tags = ['crypto', name, sym, f'{sym} price', f'{name} analysis', 'crypto analysis', 'technical analysis',
            'altcoins', 'crypto news', 'crypto shorts', 'animation', 'stick figure'] + extra
    return rnd.choice(titles), desc, tags


# ------------------------------------------------------------------ Shorts

def produce_short(kind, hist, vid, args, exclude=(), avoid_formats=()):
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
    rnd = random.Random(vid)
    fmt = args.format or formats.pick_format(hist, rnd, data, avoid_formats)
    concept = (args.concept or formats.pick_concept(hist, rnd, data)) if fmt == 'school' else None
    log(f'format: {fmt}' + (f' ({concept})' if concept else ''))
    out = OUT / vid
    out.mkdir(parents=True, exist_ok=True)
    (out / 'data.json').write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    sc = script.make_script(data, hist, fmt, seed=vid, concept=concept)
    sc['id'] = vid
    (out / 'script.json').write_text(json.dumps(sc, indent=2, ensure_ascii=False), encoding='utf-8')
    for L in sc['lines']:
        log(f"  {L['char']:>10} [{L['scene']}{'/' + L['board'] if L['scene'] == 'board' else ''}"
            f"{'/' + L['chart_action'] if L['chart_action'] != 'none' else ''}] {L['display']}")
    video = {'id': vid, 'layout': 'short', 'coins': {'a': data}, 'cast': ['charlie', data['sidekick']],
             'lines': sc['lines'], 'mood': data['mood']}
    mp4, dur, _ = render.render(video, out, preview_png=out / 'thumb.png')
    log(f'rendered {mp4} ({dur:.1f}s, script: {sc["source"]})')
    return data, sc, mp4


def fresh(data):
    """Render sonrası fiyat %3'ten fazla oynadıysa video iptal."""
    try:
        now = market.price_now(data['coin']['id'])
    except Exception as e:
        log(f'freshness check skipped: {e}'); return True
    move = abs(now / data['coingecko_price'] - 1) * 100
    log(f'freshness: {data["coingecko_price"]} -> {now} ({move:.2f}%)')
    return move <= CONFIG['freshness']['max_move_pct']


def make_short(kind, hist, args, stamp, exclude, avoid_formats=()):
    for attempt in range(2):
        vid = f'crypto_{stamp}_{kind}' + (f'_r{attempt}' if attempt else '')
        data, sc, mp4 = produce_short(kind, hist, vid, args, exclude, avoid_formats)
        if args.data or args.coin or fresh(data):
            return data, sc, mp4
        gh_annotation('warning', f"{data['coin']['symbol']} moved more than {CONFIG['freshness']['max_move_pct']}% "
                                 'since the data was pulled, rebuilding with fresh data')
    raise RuntimeError('price still moving too fast after rebuild')


# ------------------------------------------------------------------ uzun video

LONG = {
    # Moon or Doom'un kendi uzun formatları (Salı / Cuma): kalıcı arama trafiği alan anlatımlar
    'explained': dict(title='Moon or Doom Explained'),
    'school': dict(title='Chart School'),
    # Whale Market Pulse haftalık özet yapıyor -> bunlar sadece elle çalıştırılır (kitleyi bölmeyelim)
    'weekly': dict(title='Moon or Doom Weekly', labels={
        'week_gainer': ["this week's top gainer", 'the runner-up gainer', 'the third-best gainer'],
        'week_loser': ["this week's biggest loser", 'the second-biggest loser', 'the third-biggest loser']},
        board={'week_gainer': ['TOP GAINER #1', 'TOP GAINER #2', 'TOP GAINER #3'],
               'week_loser': ['TOP LOSER #1', 'TOP LOSER #2', 'TOP LOSER #3']}),
    'majors': dict(title='Big Coins Check-up'),
}
SCHOOL_LONG_TITLES = {
    'rsi': ('What Is RSI? RSI Indicator Explained With Cartoons', ['RSI', 'EXPLAINED']),
    'sr': ('Support and Resistance Explained With Cartoons', ['SUPPORT', '&', 'RESISTANCE']),
    'volume': ('Trading Volume Explained With Cartoons', ['VOLUME', 'EXPLAINED']),
    'trend': ('Moving Averages Explained With Cartoons', ['MOVING', 'AVERAGES']),
    'candles': ('How to Read Candlestick Charts (Explained With Cartoons)', ['READ', 'CANDLES']),
}


def intro_outro(kind, first, last, concept=None):
    L = formats.Lines()
    if kind == 'explained':
        L.say('charlie', 'Welcome to Moon or Doom Explained. Five trending projects, in plain English.', 'neutral', 'standing')
        L.say('moon_max', 'I only understand rockets. Please go slow.', 'excited', 'celebrate', jump=True)
        L.say('bear_betty', 'I will judge each one. Harshly.', 'smug', 'arms_crossed')
        L.say('charlie', 'Deal. What each one is, then what its chart says.', 'smug', 'standing')
    elif kind == 'school':
        lesson = formats.CONCEPTS[concept][0]
        L.say('charlie', 'Welcome to Chart School. Class is in session.', 'neutral', 'standing')
        L.say('moon_max', 'I brought a pencil! And snacks!', 'excited', 'celebrate', jump=True)
        for j, t in enumerate(formats.LESSONS_LONG[concept]):
            L.say('charlie', t, 'neutral', 'standing', 'board', board=lesson)
            if j == 2:
                L.say('moon_max', 'Okay, I am taking notes. Mentally. Mostly.', 'confused', 'thinking')
        L.say('bear_betty', 'Fine. Show me it works on real charts.', 'suspicious', 'arms_crossed')
        L.say('charlie', 'Four real examples. Let us go.', 'smug', 'standing')
    elif kind == 'weekly':
        L.say('charlie', 'Welcome to Moon or Doom Weekly. The biggest movers of the week.', 'neutral', 'standing')
        L.say('moon_max', 'Three coins that flew. I brought sunglasses!', 'excited', 'celebrate', jump=True)
        L.say('bear_betty', 'And three that fell. I brought popcorn.', 'smug', 'arms_crossed')
        L.say('charlie', 'Same rules as always. Charts, levels, no promises.', 'smug', 'standing')
    else:
        L.say('charlie', 'Welcome to the Big Coins Check-up. The largest coins, their key levels.', 'neutral', 'standing')
        L.say('moon_max', 'The big boys! My favorite rockets!', 'excited', 'celebrate', jump=True)
        L.say('bear_betty', 'Big coins. Big falls. I am listening.', 'smug', 'arms_crossed')
        L.say('charlie', 'Charts and levels only. Let us start at the top.', 'smug', 'standing')
    O = formats.Lines()
    O.say('moon_max', 'That was the best episode ever. Again.', 'happy', 'hips')
    O.say('bear_betty', 'It had charts. I will allow it.', 'smug', 'arms_crossed')
    O.say('charlie', ('Class dismissed. ' if kind == 'school' else 'See you next time. ') +
          'Levels, not promises. Not financial advice.', 'neutral', 'standing')
    L, O = list(L.trim(99)), list(O.trim(99))
    for L_ in L:
        L_['coin'] = first
    for L_ in O:
        L_['coin'] = last
    return L, O


def seg_labels(kind, d, i, counters):
    """-> (konuşmadaki etiket [yer tutucu olabilir], pano/bölüm başlığı)"""
    if kind == 'explained':
        if d.get('trending_rank'):
            return 'number {RANK} on CoinGecko trending', f"TRENDING #{d['trending_rank']}"
        return "one of today's biggest movers", "TODAY'S MOVER"
    if kind == 'school':
        if i == 0:
            return 'the biggest coin by market cap', 'EXAMPLE #1'
        return ('up {CHANGE} today' if d['change_24h_pct'] >= 0 else 'down {CHANGE} today'), f'EXAMPLE #{i + 1}'
    if kind == 'weekly':
        spec = LONG['weekly']
        n = counters.get(d['reason_trending'], 0); counters[d['reason_trending']] = n + 1
        return spec['labels'][d['reason_trending']][n], spec['board'][d['reason_trending']][n]
    return 'ranked {MCAPRANK} by market cap', f"MARKET CAP #{d['coin'].get('market_cap_rank')}"


def pick_long_concept(hist, rnd):
    recent = [v.get('concept') for v in hist.get('videos', []) if v.get('kind') == 'school'][-3:]
    return rnd.choice([c for c in formats.CONCEPTS if c not in recent] or list(formats.CONCEPTS))


def produce_long(kind, hist, args, stamp):
    vid = f'long_{kind}_{stamp}'
    out = OUT / vid
    out.mkdir(parents=True, exist_ok=True)
    datas = picker.pick_long(kind, vid, hist)
    if len(datas) < 3:
        raise RuntimeError(f'only {len(datas)} coins available for {kind}')
    rnd = random.Random(vid)
    concept = (args.concept or pick_long_concept(hist, rnd)) if kind == 'school' else None
    if concept:
        log(f'concept: {concept}')
    title_base = LONG[kind]['title']
    coins, lines, sources, counters = {}, [], [], {}
    for i, d in enumerate(datas):
        key = f'c{i + 1}'
        coins[key] = d
        label, board = seg_labels(kind, d, i, counters)
        seg, src = script.make_segment(d, key, label, title_base, seed=f'{vid}_{key}', kind=kind, concept=concept)
        sources.append(src)
        seg[0]['segment_start'] = True
        chg = d.get('change_7d_pct') if kind in ('weekly', 'majors') and d.get('change_7d_pct') is not None \
            else d['change_24h_pct']
        name = f"{d['coin']['name']} ({d['coin']['symbol']})"
        seg[0]['chapter'] = {'explained': f'What is {name}?', 'school': f'Example: {name}'}.get(
            kind, f"{name} {signed(chg)} — {board.title()}")
        for L in seg:
            L['label'] = board
        lines += seg
        log(f"segment {key}: {d['coin']['symbol']} {board} ({src}, {len(seg)} lines)")
    intro, outro = intro_outro(kind, 'c1', f'c{len(datas)}', concept)
    script.expand(intro, datas[0], 'c1')
    script.expand(outro, datas[-1], f'c{len(datas)}')
    for L in intro + outro:
        L.setdefault('chart_action', 'none')
        L['label'] = 'CHART SCHOOL' if kind == 'school' else title_base.upper()
    intro[0]['chapter'] = 'The lesson' if kind == 'school' else 'Intro'
    outro[0]['segment_start'] = True
    outro[0]['chapter'] = 'Wrap-up'
    lines = intro + lines + outro
    (out / 'data.json').write_text(json.dumps(datas, indent=1, ensure_ascii=False), encoding='utf-8')
    (out / 'script.json').write_text(json.dumps(lines, indent=2, ensure_ascii=False), encoding='utf-8')
    video = {'id': vid, 'layout': 'long', 'coins': coins, 'cast': ['charlie', 'moon_max', 'bear_betty'],
             'lines': lines, 'mood': 'bullish'}
    mp4, dur, chapters = render.render(video, out, preview_png=out / 'preview.png')
    log(f'rendered {mp4} ({dur / 60:.1f} min, scripts: {sources})')
    today = datetime.now(timezone.utc)
    syms = [d['coin']['symbol'] for d in datas]
    if kind == 'explained':
        names = [d['coin']['name'] for d in datas]
        n = len(datas)
        title = f"What Are {', '.join(names[:-1])} and {names[-1]}? {n} Trending Crypto Projects Explained"
        if len(title) > 100:
            title = f"What Are {', '.join(syms[:-1])} and {syms[-1]}? {n} Trending Crypto Projects Explained (Cartoon)"
        thumb_title, thumb_sub = ['WHAT', 'ARE', 'THESE?'], ' · '.join(syms).split()
        intro_txt = (f'{n} crypto projects trending right now, explained in plain English by Chart Charlie, Moon Max '
                     'and Bear Betty: what each project does, what its token is for, and the support and resistance '
                     'levels on its 4H chart.')
        tags = ['what is crypto', 'crypto explained', 'crypto for beginners', 'trending crypto', 'altcoins explained',
                'crypto projects', 'animation', 'cartoon'] + [f"what is {d['coin']['name']}" for d in datas] + \
               [d['coin']['name'] for d in datas]
    elif kind == 'school':
        base, thumb_title = SCHOOL_LONG_TITLES[concept]
        title = f"{base} | {', '.join(syms[:-1])} & {syms[-1]} Examples"
        thumb_sub = 'CHART SCHOOL · 3 REAL EXAMPLES'.split()
        intro_txt = (f"Chart School: {formats.CONCEPTS[concept][1].lower()}, explained with cartoons and applied to three "
                     f"real charts ({', '.join(syms)}). Beginner friendly, no jargon.")
        tags = [formats.CONCEPTS[concept][1].lower(), 'technical analysis for beginners', 'how to read crypto charts',
                'trading basics', 'crypto for beginners', 'chart school', 'animation', 'cartoon'] + \
               [d['coin']['name'] for d in datas]
    elif kind == 'weekly':
        span = f"{(today - timedelta(days=7)).strftime('%b %d')} – {today.strftime('%b %d')}"
        title = f"Top Crypto Gainers & Losers This Week ({span}) | Moon or Doom Weekly"
        thumb_title, thumb_sub = ['WEEKLY', 'MOVERS'], 'TOP 3 GAINERS & TOP 3 LOSERS'.split()
        intro_txt = 'The biggest gainers and losers of the week among large coins, with their 4H chart levels.'
        tags = ['crypto weekly', 'top gainers', 'top losers'] + [d['coin']['name'] for d in datas]
    else:
        title = f"{', '.join(syms)}: Support & Resistance Levels ({today.strftime('%b %d')}) | Big Coins Check-up"
        thumb_title, thumb_sub = ['BIG', 'COINS', 'CHECK-UP'], 'KEY LEVELS FOR THE TOP 5'.split()
        intro_txt = 'The five largest coins by market cap and the support and resistance levels on the 4H chart.'
        tags = ['bitcoin', 'ethereum', 'crypto analysis'] + [d['coin']['name'] for d in datas]
    tags += ['crypto', 'technical analysis', 'support and resistance', 'Moon or Doom']
    thumbs.make(out / 'thumb.png', thumb_title, thumb_sub, datas)
    chap = '\n'.join(f"{int(s // 60)}:{int(s % 60):02d} {c}" for s, c in [(0, chapters[0][1])] + chapters[1:])
    lv = '\n\n'.join(f"{d['coin']['name']} ({d['coin']['symbol']})\n" + '\n'.join(levels_block(d)) for d in datas)
    desc = (intro_txt + '\n\nChapters:\n' + chap + '\n\n' + lv + '\n\n' + FOOTER +
            'Moon or Doom: daily top gainer & loser Shorts, plus Explained (Tuesday) and Chart School (Friday).\n'
            '#crypto #MoonOrDoom #altcoins')
    (out / 'meta.json').write_text(json.dumps({'title': title, 'description': desc, 'tags': tags}, indent=2,
                                              ensure_ascii=False), encoding='utf-8')
    return vid, datas, mp4, title, desc, tags, out / 'thumb.png', concept


# ------------------------------------------------------------------ yükleme + kayıt

def record(hist, entry):
    hist.setdefault('videos', []).append(dict(entry, date=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')))
    hist['videos'] = hist['videos'][-300:]
    HIST.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding='utf-8')


def to_playlist(upload, key, video_id):
    pls = json.loads((HERE / 'playlists.json').read_text(encoding='utf-8')) if (HERE / 'playlists.json').exists() else {}
    if key in pls:
        try:
            upload.add_to_playlist(pls[key], video_id); log(f'added to playlist {key}')
        except Exception as e:
            log(f'playlist add skipped: {str(e)[:160]}')


ENGAGE = {
    'levels': ['🚀 Moon or 💀 Doom for {SYM}? Drop one emoji 👇', 'Which level breaks first for {SYM}? 👇'],
    'what_is': ['Had you heard of {NAME} before this? 👀', 'Which project should Charlie explain next? 👇'],
    'school': ['What should Chart School cover next? RSI, volume, candles…? 👇', 'Did that make sense? Rate the lesson 1-10 👇'],
    'skit': ['Are you Team Max 🚀 or Team Betty 💀? 👇', 'Who was right today, Max or Betty? 👇'],
    'long': ['Which project should we explain next? 👇', 'What should Chart School cover next? 👇'],
}


def engage(upload, video_id, fmt, data):
    """Etkileşim sorusu olan bir kanal yorumu (yorum sinyali algoritma için önemli). Başarısızsa sessizce geçer."""
    try:
        t = random.choice(ENGAGE.get(fmt, ENGAGE['levels'])).format(SYM=data['coin']['symbol'], NAME=data['coin']['name'])
        upload.comment(video_id, t)
        log(f'comment posted: {t}')
    except Exception as e:
        log(f'comment skipped: {str(e)[:160]}')


def run_long(kind, args, mode, hist):
    import upload
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')
    try:
        vid, datas, mp4, title, desc, tags, thumb, concept = produce_long(kind, hist, args, stamp)
    except Exception as e:
        traceback.print_exc(); gh_annotation('error', f'long video failed: {e}'); raise SystemExit(1)
    log(f'title: {title}')
    if mode == 'off':
        log('upload skipped (mode off)'); return
    try:
        video_id = upload.upload(mp4, title, desc, tags, mode, category='27')
    except Exception as e:
        traceback.print_exc(); gh_annotation('error', f'upload failed: {e}'); raise SystemExit(1)
    url = f'https://youtu.be/{video_id}'
    log(f'uploaded {url} ({mode})')
    try:
        upload.set_thumbnail(video_id, thumb); log('thumbnail set')
    except Exception as e:
        log(f'thumbnail skipped (phone-verify the channel to enable): {str(e)[:160]}')
    record(hist, {'id': vid, 'kind': kind, 'coins': [d['coin']['id'] for d in datas], 'video_id': video_id,
                  'privacy': mode, 'title': title, 'format': 'long', 'concept': concept})
    to_playlist(upload, 'long', video_id)
    engage(upload, video_id, 'long', datas[0])
    notify.message(f'✅ {title}\n{url} ({mode})')


def social_captions(title, data):
    """TikTok / Instagram açıklamaları. Finans içeriği: her ikisinde de 'yatırım tavsiyesi değildir' notu."""
    sym = re.sub(r'[^A-Za-z0-9]', '', data['coin']['symbol'].upper())
    note = 'Not financial advice. Entertainment & education only. Do your own research.'
    tiktok = f"{title}\n\n{note}\n\n#crypto #{sym} #cryptonews #altcoins #learnontiktok #fyp"
    insta = (f"{title}\n\nFollow for a daily crypto mover breakdown 🌕💀\n{note}\n\n"
             f"#crypto #bitcoin #cryptocurrency #{sym} #altcoins")  # Instagram: en fazla 5, en geniş erişimli
    return tiktok, insta


def send_social(mp4, title, url, data):
    tiktok, insta = social_captions(title, data)
    # fenek-shorts'taki telegram-relay bu klasörü (artifact 'social-<run>') alıp Fenek botuyla gönderir
    soc = HERE / 'social'
    soc.mkdir(exist_ok=True)
    shutil.copy(mp4, soc / 'video.mp4')
    (soc / 'post.json').write_text(json.dumps({'channel': 'Moon or Doom', 'title': title, 'url': url, 'tiktok': tiktok,
                                               'instagram': insta}, ensure_ascii=False, indent=1), encoding='utf-8')
    notify.document(mp4, f'🎬 Moon or Doom — günün videosu (TikTok/Instagram için)\n{title}\n{url}')
    notify.copyable('🎵 TikTok açıklaması (kutuya dokun → kopyalanır):', tiktok)
    notify.copyable('📸 Instagram açıklaması (kutuya dokun → kopyalanır):', insta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-upload', action='store_true')
    ap.add_argument('--only', choices=picker.KINDS, help='sadece yükselen ya da sadece düşen')
    ap.add_argument('--format', choices=list(SHORT_FORMATS), help='Shorts formatını zorla')
    ap.add_argument('--concept', choices=list(CONCEPTS), help='school formatında konu')
    ap.add_argument('--coin', help='CoinGecko id (seçimi atla, tek video)')
    ap.add_argument('--data', help='hazır data.json ile render (tek video)')
    ap.add_argument('--long', choices=list(LONG), help='uzun video: explained | school (weekly | majors elle)')
    args = ap.parse_args()
    import upload

    mode = privacy_mode(args.no_upload)
    hist = picker.load_hist(HIST)
    if mode != 'off':
        try:
            log(f'channel check ok: {upload.check_channel()}')
        except Exception as e:
            gh_annotation('error', f'channel check failed, nothing uploaded: {e}'); raise SystemExit(1)
    if args.long:
        return run_long(args.long, args, mode, hist)

    kinds = ['manual'] if args.coin or args.data else [args.only] if args.only else list(picker.KINDS)
    if len(kinds) > 1:  # slot başına tek video: yükselen ve düşen sırayla (hacim = şablon sinyali)
        last = next((v.get('kind') for v in reversed(hist.get('videos', [])) if v.get('kind') in picker.KINDS), None)
        kinds = [k for k in kinds if k != last][:1] or kinds[:1]
    log(f"videos: {', '.join(kinds)} | upload mode: {mode}")
    if mode != 'off':
        left = CONFIG['daily_videos'] - today_count(hist)
        if left <= 0:
            log(f"daily cap of {CONFIG['daily_videos']} reached, nothing to do"); return
        kinds = kinds[:left]

    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')
    gap = CONFIG['pair_gap_minutes'] * 60
    failed, last_upload, used, used_formats, used_titles = False, None, [], [], []
    for kind in kinds:
        try:
            data, sc, mp4 = make_short(kind, hist, args, stamp, used, used_formats)
            used_formats.append(sc['format'])
        except SystemExit:
            raise
        except Exception as e:
            traceback.print_exc(); gh_annotation('error', f'{kind} video failed: {e}'); failed = True; continue
        used.append(data['coin']['id'])
        title, desc, tags = metadata(data, sc, random.Random(data['id']),
                                     [v.get('title') for v in hist['videos'][-12:]] + used_titles)
        used_titles.append(title)
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
        record(hist, {'id': data['id'], 'coin': data['coin']['id'], 'symbol': data['coin']['symbol'],
                      'price': data['coingecko_price'], 'change_24h_pct': data['change_24h_pct'], 'kind': kind,
                      'format': sc['format'], 'concept': sc.get('concept'), 'hook': sc['hook'], 'punch': sc['punch'],
                      'script': sc['source'], 'video_id': video_id, 'privacy': mode, 'title': title})
        to_playlist(upload, kind, video_id)
        engage(upload, video_id, sc['format'], data)
        if today_count(hist) == 1:  # Telegram'a günde tek video: günün ilk Shorts'u (TikTok/Instagram için)
            send_social(mp4, title, url, data)
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
