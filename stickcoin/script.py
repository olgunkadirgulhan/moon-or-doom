"""Senaryo: Gemini yazar (yer tutucularla) -> doğrulama -> en fazla 2 yeniden deneme -> olmazsa kural tabanlı şablon.

Temel kural (Bölüm 1): LLM sayı yazamaz. Metinde rakam veya sayı kelimesi varsa senaryo reddedilir;
sayılar yalnızca {R1} gibi yer tutuculardan gelir ve koddaki doğrulanmış veriyle doldurulur.
"""
import json
import os
import random
import re
import time

import requests

from . import ROOT, words
from .cast import CAST, CHART_ACTIONS, EMOTIONS, POSES

MODELS = 'gemini-3.8-flash,gemini-3.5-flash,gemini-flash-latest,gemini-3-flash-preview,gemini-flash-lite-latest'
HOOKS = {
    'question': 'a loud, panicked or greedy QUESTION about the move (e.g. "is it too late?!").',
    'bold_claim': 'an absurd, over-the-top BOLD CLAIM about the move.',
    'reaction': 'a pure emotional REACTION, screaming at the number.',
}
PUNCHES = {
    'reality_check': 'the sidekick says something wildly emotional; Charlie deflates it with one dry fact.',
    'role_reversal': 'the sidekick unexpectedly flips (Max gets scared / Betty gets hopeful); Charlie reacts dryly.',
    'callback': "the sidekick repeats the hook's idea; Charlie answers with a dry one-liner callback.",
}
BANNED = [
    (re.compile(r'\b(buy|sell|buying|selling)\b', re.I), 'buy/sell advice'),
    (re.compile(r"guarantee|can'?t lose|cannot lose|\b\d+x\b|will (hit|reach|go to)|price target", re.I), 'promise'),
    (re.compile(r'\b(binance|coinbase|bybit|okx|kucoin|kraken|referral|promo code|sign ?up)\b', re.I), 'promotion'),
    (re.compile(r'\b(dollars?|cents?|bucks|percent|hundred|thousand|million|billion|trillion|ten|eleven|twelve|'
                r'\w+teen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b', re.I), 'number word'),
    (re.compile(r'\d'), 'raw digit'),
]
PH = re.compile(r'\{([A-Z0-9_]+)\}')


def log(m):
    print(f'[script] {m}', flush=True)


# ------------------------------------------------------------------ Gemini

def gemini(prompt, temperature=0.9, timeout=120):
    key = (os.environ.get('GEMINI_API_KEY') or '').strip().lstrip('﻿')
    if not key:
        raise RuntimeError('GEMINI_API_KEY not set')
    models = [m.strip() for m in (os.environ.get('GEMINI_MODELS') or MODELS).split(',') if m.strip()]
    body = {'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': temperature, 'responseMimeType': 'application/json'}}
    errors = []
    for attempt in range(2):
        for model in models:
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            try:
                r = requests.post(url, json=body, headers={'x-goog-api-key': key}, timeout=timeout)
            except requests.RequestException as e:
                errors.append(f'{model}:{type(e).__name__}'); continue
            if r.status_code == 200:
                parts = r.json()['candidates'][0]['content']['parts']
                return ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
            errors.append(f'{model}:{r.status_code}')
            if r.status_code not in (404, 429, 500, 503):
                r.raise_for_status()
        time.sleep(15)
    raise RuntimeError(f"Gemini unavailable: {', '.join(errors)}")


def parse_json(text):
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    return json.loads(text[text.find('{'): text.rfind('}') + 1])


# ------------------------------------------------------------------ doğrulama (Bölüm 8)

def validate(sc, data):
    """-> sorun listesi (boşsa geçerli). Eksik/uydurma alanlar güvenli varsayılana çekilir."""
    ph = words.placeholders(data)
    side = data['sidekick']
    lines = sc.get('lines') or []
    problems = []
    if not 8 <= len(lines) <= 12:
        problems.append(f'{len(lines)} lines (want 8-12)')
    seen_actions = {}
    for i, L in enumerate(lines):
        text = (L.get('text') or '').strip()
        L['text'] = text
        if L.get('char') not in ('charlie', side):
            problems.append(f"line {i + 1}: unknown character {L.get('char')}")
        L['emotion'] = L.get('emotion') if L.get('emotion') in EMOTIONS else 'neutral'
        L['pose'] = L.get('pose') if L.get('pose') in POSES else None
        L['chart_action'] = L.get('chart_action') if L.get('chart_action') in CHART_ACTIONS else 'none'
        L['jump'] = bool(L.get('jump')) and L.get('char') == side
        for key in PH.findall(text):
            if key not in ph:
                problems.append(f'line {i + 1}: unknown or unavailable placeholder {{{key}}}')
        bare = PH.sub('X', text)
        low = bare.lower().replace('not financial advice', '')
        for rx, why in BANNED:
            m = rx.search(low if why != 'raw digit' else bare)
            if m:
                problems.append(f'line {i + 1}: {why} "{m.group(0)}" in: {text}')
        if 'financial advice' in low:
            problems.append(f'line {i + 1}: "financial advice" outside the disclaimer')
        n_words = len(expand_text(text, ph)[0].split())
        if n_words > 14:
            problems.append(f'line {i + 1}: {n_words} words (max 14): {text}')
        act = L['chart_action']
        if act != 'none':
            if act in seen_actions:
                problems.append(f'chart_action {act} used twice')
            seen_actions[act] = i
    if problems:
        return problems
    if lines[0]['char'] != side:
        problems.append(f'first line must be the {side} hook')
    if '{SYMBOL}' not in lines[0]['text'] and '{NAME}' not in lines[0]['text']:
        problems.append('hook must mention {SYMBOL}')
    if lines[-1]['char'] != 'charlie' or not lines[-1]['text'].lower().rstrip('.! ').endswith('not financial advice'):
        problems.append('last line must be charlie ending with "Not financial advice."')
    need = {'show': None, 'draw_resistance': '{R1}', 'draw_support': '{S1}'}
    if 'R2' in ph:
        need['highlight_scenario_up'] = '{R2}'
    if 'S2' in ph:
        need['highlight_scenario_down'] = '{S2}'
    for act, token in need.items():
        if act not in seen_actions:
            problems.append(f'missing chart_action {act}')
            continue
        L = lines[seen_actions[act]]
        if act != 'show' and L['char'] != 'charlie':
            problems.append(f'{act} must be spoken by charlie')
        if token and token not in L['text']:
            problems.append(f'the {act} line must contain {token}')
    for act in ('highlight_scenario_up', 'highlight_scenario_down'):
        if act in seen_actions and act not in need:
            problems.append(f'{act} needs a second level that does not exist')
    if 'show' in seen_actions and seen_actions['show'] > 3:
        problems.append('chart must appear (show) within the first 4 lines')
    order = [seen_actions.get(a) for a in ('show', 'draw_resistance', 'draw_support')]
    if None not in order and not order[0] < min(order[1:]):
        problems.append('show must come before drawing levels')
    return problems


def expand_text(text, ph):
    display = PH.sub(lambda m: ph[m.group(1)][0] if m.group(1) in ph else m.group(0), text)
    say = PH.sub(lambda m: ph[m.group(1)][1] if m.group(1) in ph else m.group(0), text)
    return display, say


def expand(sc, data):
    """Yer tutucuları doldurur; her replik için [(ekranda, okunuş)] token listesi üretir."""
    ph = words.placeholders(data)
    for L in sc['lines']:
        toks = []
        for raw in L['text'].split():
            d, s = expand_text(raw, ph)
            toks.append((d, s))
        L['tokens'] = toks
        L['display'] = ' '.join(d for d, _ in toks)
    return sc


# ------------------------------------------------------------------ bağlam

def rsi_zone(r):
    if r is None:
        return 'unknown'
    return 'overbought' if r >= 70 else 'oversold' if r <= 30 else 'hot but not overbought' if r >= 60 \
        else 'weak but not oversold' if r <= 40 else 'neutral'


def trend_text(data):
    p, e50, e200 = data['price'], data.get('ema_50'), data.get('ema_200')
    if e50 is None or e200 is None:
        return 'unclear'
    if p > e50 > e200:
        return 'price above both the 50 and 200 EMA on the 4h chart (uptrend)'
    if p < e50 < e200:
        return 'price below both the 50 and 200 EMA on the 4h chart (downtrend)'
    return 'price chopping between the 50 and 200 EMA (mixed trend)'


def mover_line(data):
    """Neden ekranda: günün en çok yükseleni / düşeni (sırası 1 değilse 'one of')."""
    r, first, up = data['reason_trending'], data.get('mover_rank') == 1, data['change_24h_pct'] >= 0
    if r == 'top_gainer_24h':
        return "{NAME} is today's biggest gainer among large coins." if first else \
            "{NAME} is one of today's biggest gainers among large coins."
    if r == 'top_loser_24h':
        if up:
            return '{NAME} is the weakest large coin today, even in a green market.'
        return "{NAME} is today's biggest loser among large coins." if first else \
            "{NAME} is one of today's biggest losers among large coins."
    return '{NAME} is on our radar today.'


def why_hint(data):
    hint = mover_line(data).replace('{NAME} is', 'it is').rstrip('.')
    if data.get('trending_rank'):
        hint += ', and it is {RANK} on CoinGecko trending'
    if data.get('volume_vs_avg'):
        hint += ', volume is {VOLX} its recent average'
    return hint


# ------------------------------------------------------------------ Gemini senaryosu

def write_with_gemini(data, hook, punch, attempts=3):
    side = data['sidekick']
    ph = words.placeholders(data)
    scen = ['   - a charlie line with chart_action "highlight_scenario_up": if it breaks {R1} -> next level {R2}'
            if 'R2' in ph else '   - a charlie line (chart_action "none"): if it breaks {R1}, what happens (no new level)',
            '   - a charlie line with chart_action "highlight_scenario_down": if it loses {S1} -> watch {S2}'
            if 'S2' in ph else '   - a charlie line (chart_action "none"): if it loses {S1}, what happens (no new level)']
    context = {k: data.get(k) for k in ('price', 'change_24h_pct', 'change_7d_pct', 'volume_vs_avg', 'rsi_14',
                                        'resistance_1', 'resistance_2', 'support_1', 'support_2', 'mood')}
    base = (ROOT / 'prompts' / 'script_crypto.txt').read_text(encoding='utf-8').format(
        charlie_bio=CAST['charlie']['bio'], sidekick=side, sidekick_name=CAST[side]['name'],
        sidekick_bio=CAST[side]['bio'], name=data['coin']['name'], symbol=data['coin']['symbol'],
        reason=data['reason_trending'], context=json.dumps(context),
        placeholders='\n'.join(f'  {{{k}}} = {v[0]}' for k, v in ph.items()),
        hook_style=HOOKS[hook], why_hint=why_hint(data), rsi_zone=rsi_zone(data.get('rsi_14')),
        trend=trend_text(data), scenario_rules='\n'.join(scen), punch_style=PUNCHES[punch],
        emotions=', '.join(EMOTIONS), poses=', '.join(POSES))
    feedback = ''
    for attempt in range(attempts):
        try:
            sc = parse_json(gemini(base + feedback))
        except Exception as e:
            log(f'attempt {attempt + 1} failed: {str(e)[:200]}'); continue
        problems = validate(sc, data)
        if not problems:
            log(f'Gemini script accepted on attempt {attempt + 1}')
            return sc
        log(f'attempt {attempt + 1} rejected: {problems[:3]}')
        feedback = ('\n\nYour previous script was REJECTED for: ' + '; '.join(problems[:6]) +
                    '. Fix every issue. Remember: no digits and no number words, placeholders only.')
    return None


# ------------------------------------------------------------------ kural tabanlı şablon (yedek)

def template_script(data, hook, punch, rnd):
    side = data['sidekick']
    bull = side == 'moon_max'
    ph = words.placeholders(data)
    hooks = {
        True: {'question': '{SYMBOL} just pumped {CHANGE}! Is it too late?!',
               'bold_claim': "{SYMBOL} is up {CHANGE}! I'm naming my firstborn after it!",
               'reaction': 'WHAT?! {SYMBOL} up {CHANGE} in a day?! Fuel the rocket!'},
        False: {'question': '{SYMBOL} dumped {CHANGE}. Still think crypto is the future, Charlie?',
                'bold_claim': "{SYMBOL} is down {CHANGE}. Told you. It's going to zero.",
                'reaction': 'Down {CHANGE}? {SYMBOL} holders, I have one word for you. Ouch.'},
    }
    L = []

    def say(char, text, emotion='neutral', pose=None, act='none', jump=False):
        L.append({'char': char, 'text': text, 'emotion': emotion, 'pose': pose, 'chart_action': act, 'jump': jump})

    say(side, hooks[bull][hook], 'excited' if bull else 'smug', 'celebrate' if bull else 'arms_crossed', jump=bull)
    say('charlie', mover_line(data), 'neutral', 'standing')
    if 'VOLX' in ph:
        say('charlie', 'Volume is running {VOLX} its recent average. Here is the chart.', 'neutral', 'pointing', 'show')
    else:
        say('charlie', 'Here is the four-hour chart for the past week.', 'neutral', 'pointing', 'show')
    say('charlie', rnd.choice(['First wall: resistance at {R1}.', 'Resistance sits at {R1}. Sellers showed up there before.',
                               'Above us, the key resistance is {R1}.']), 'neutral', 'pointing', 'draw_resistance')
    say('charlie', rnd.choice(['Below, support at {S1}. Buyers defended it before.', 'Support is {S1}. That is the floor to watch.',
                               'The floor to watch is {S1}.']), 'neutral', 'pointing', 'draw_support')
    if bull:
        say(side, rnd.choice(['Resistance? Never heard of her.', 'Walls are just ramps for rockets!']), 'excited', 'hips')
    else:
        say(side, rnd.choice(['Support? Like my ex. Never there when you need it.', 'Floors are just future ceilings.']),
            'suspicious', 'arms_crossed')
    if 'RSI' in ph:
        zone = rsi_zone(data['rsi_14'])
        say('charlie', {'overbought': 'RSI is {RSI}. That is overbought, so pullbacks would not shock me.',
                        'oversold': 'RSI is {RSI}. That is oversold, where relief bounces often start.'}.get(
            zone, 'RSI is {RSI}, so momentum reads ' + zone + '.'), 'thinking', 'thinking')
    if 'R2' in ph:
        say('charlie', 'If it breaks {R1} with volume, the next level to watch is {R2}.', 'neutral', 'pointing',
            'highlight_scenario_up')
    else:
        say('charlie', 'If it breaks {R1}, there is little overhead on this chart.', 'neutral', 'pointing')
    if 'S2' in ph:
        say('charlie', 'If it loses {S1}, watch {S2} next.', 'neutral', 'pointing', 'highlight_scenario_down')
    else:
        say('charlie', 'If it loses {S1}, the chart gets a lot uglier.', 'neutral', 'pointing')
    punches = {
        True: {'reality_check': [('So... moon tomorrow?', 'excited'), ('Maybe. Or maybe the rocket needs a refuel.', 'smug')],
               'role_reversal': [('Okay I am scared now. Hold me.', 'cry'), ('It went up. Why are you crying?', 'confused')],
               'callback': [('So it is NOT too late?!', 'excited'), ('Late is a feeling. Levels are levels.', 'smug')]},
        False: {'reality_check': [('Going to zero. Mark my words.', 'smug'), ('Noted. {S1} comes first, then we talk zero.', 'smug')],
                'role_reversal': [('Fine. Maybe I will watch {S1}. Quietly.', 'nervous'), ('Growth. I am proud of you.', 'happy')],
                'callback': [('Still think crypto is the future?', 'suspicious'), ('I think {S1} is the present.', 'smug')]},
    }
    (t1, e1), (t2, e2) = punches[bull][punch]
    say(side, t1, e1, 'crying' if e1 == 'cry' else ('celebrate' if bull else 'arms_crossed'), jump=bull and e1 == 'excited')
    say('charlie', t2, e2, 'shrug' if e2 == 'confused' else 'standing')
    say('charlie', 'Levels, not promises. Not financial advice.', 'neutral', 'standing')
    # 12'yi aşarsa itiraz satırını çıkar
    while len(L) > 12:
        L.pop(5)
    return {'lines': L}


# ------------------------------------------------------------------ giriş noktası

def make_script(data, hist, seed=None):
    rnd = random.Random(seed)
    recent = hist.get('videos', [])[-3:]
    hook = rnd.choice([h for h in HOOKS if h not in {v.get('hook') for v in recent[-1:]}])
    punch = rnd.choice([p for p in PUNCHES if p not in {v.get('punch') for v in recent[-1:]}])
    sc = None
    source = 'template'
    prefer = (os.environ.get('SCRIPT_SOURCE') or '').lower()
    if os.environ.get('GEMINI_API_KEY') and prefer != 'template':
        try:
            sc = write_with_gemini(data, hook, punch)
            source = 'gemini'
        except Exception as e:
            log(f'Gemini failed: {str(e)[:200]}')
        if sc is None:
            log('::warning::Gemini scripts failed validation, using the rule-based template')
    if sc is None:
        sc = template_script(data, hook, punch, rnd)
        source = 'template'
        problems = validate(sc, data)
        if problems:
            raise RuntimeError(f'template script invalid: {problems}')
    sc.update(hook=hook, punch=punch, source=source)
    return expand(sc, data)
