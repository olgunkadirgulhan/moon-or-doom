"""Senaryo: Gemini yazar (formatın yapısıyla, yer tutucularla) -> doğrulama -> en fazla 2 yeniden deneme -> olmazsa şablon.

Temel kural (Bölüm 1): LLM sayı yazamaz. Metinde rakam veya sayı kelimesi varsa senaryo reddedilir;
sayılar yalnızca {R1} gibi yer tutuculardan gelir ve koddaki doğrulanmış veriyle doldurulur.
"""
import json
import os
import random
import re
import time

import requests

from . import ROOT, formats, words
from .cast import CAST, CHART_ACTIONS, EMOTIONS, POSES
from .formats import CONCEPTS, HOOKS, LONG_SEGMENT, PUNCHES, SCENES, SHORT_FORMATS

MODELS = 'gemini-3.8-flash,gemini-3.5-flash,gemini-flash-latest,gemini-3-flash-preview,gemini-flash-lite-latest'
BANNED = [
    (re.compile(r'\b(buy|sell|buying|selling)\b', re.I), 'buy/sell advice'),
    (re.compile(r"too late|don'?t miss|get in now|hold or fold|price target|financial freedom|get rich", re.I), 'FOMO/advice'),
    (re.compile(r"guarantee|can'?t lose|cannot lose|will (hit|reach|go to)", re.I), 'promise'),
    (re.compile(r'\b(binance|coinbase|bybit|okx|kucoin|kraken|referral|promo code|sign ?up)\b', re.I), 'promotion'),
    (re.compile(r'\b(dollars?|cents?|bucks|percent|hundred|thousand|million|billion|trillion|ten|eleven|twelve|'
                r'\w+teen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b', re.I), 'number word'),
    (re.compile(r'\d'), 'raw digit'),
]
PH = re.compile(r'\{([A-Z0-9_]+)\}')


def log(m):
    print(f'[script] {m}', flush=True)


# ------------------------------------------------------------------ Gemini

def gemini(prompt, temperature=0.95, timeout=120):
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


# ------------------------------------------------------------------ doğrulama

def board_list(spec, lesson_board):
    """Formatın izin verdiği panolar; 'LESSON' = konunun ders panosu."""
    if not spec['boards']:
        return [lesson_board]
    return [lesson_board if b == 'LESSON' else b for b in spec['boards']]


def validate(sc, data, spec, segment=False, lesson_board=None):
    """-> sorun listesi (boşsa geçerli). Eksik alanlar güvenli varsayılana çekilir."""
    ph = words.placeholders(data)
    side = data['sidekick']
    allowed_chars = ('charlie', side)
    boards = board_list(spec, lesson_board)
    lines = sc.get('lines') or []
    problems = []
    lo, hi = spec['lines']
    if not lo <= len(lines) <= hi:
        problems.append(f'{len(lines)} lines (want {lo}-{hi})')
    seen = {}
    prev_scene = 'board' if segment else 'stage'
    for i, L in enumerate(lines):
        text = (L.get('text') or '').strip()
        L['text'] = text
        if L.get('char') not in allowed_chars:
            problems.append(f"line {i + 1}: unknown character {L.get('char')}")
        L['emotion'] = L.get('emotion') if L.get('emotion') in EMOTIONS else 'neutral'
        L['pose'] = L.get('pose') if L.get('pose') in POSES else None
        L['chart_action'] = L.get('chart_action') if L.get('chart_action') in CHART_ACTIONS else 'none'
        L['jump'] = bool(L.get('jump')) and L.get('char') == side
        scene = L.get('scene') if L.get('scene') in SCENES else prev_scene
        if L['chart_action'] != 'none':
            scene = 'chart'
        if scene == 'chart' and 'show' not in seen and L['chart_action'] != 'show':
            scene = 'board' if 'board' in SCENES else 'stage'  # grafik henüz açılmadı
        if scene == 'board' and L.get('board') not in boards:
            L['board'] = boards[0]
        L['scene'] = prev_scene = scene
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
            if act in seen:
                problems.append(f'chart_action {act} used twice')
            seen[act] = i
    if problems:
        return problems
    if not segment:
        if not any(t in lines[0]['text'] for t in ('{SYMBOL}', '{NAME}')):
            problems.append('hook (line 1) must mention {SYMBOL}')
        if lines[-1]['char'] != 'charlie' or not lines[-1]['text'].lower().rstrip('.! ').endswith('not financial advice'):
            problems.append('last line must be charlie ending with "Not financial advice."')
    need = {'show': None, 'draw_resistance': '{R1}', 'draw_support': '{S1}'}
    if spec['scenarios']:
        if 'R2' in ph:
            need['highlight_scenario_up'] = '{R2}'
        if 'S2' in ph:
            need['highlight_scenario_down'] = '{S2}'
    for act, token in need.items():
        if act not in seen:
            problems.append(f'missing chart_action {act}')
            continue
        L = lines[seen[act]]
        if act != 'show' and L['char'] != 'charlie':
            problems.append(f'{act} must be spoken by charlie')
        if token and token not in L['text']:
            problems.append(f'the {act} line must contain {token}')
    if 'highlight_scenario_up' in seen and 'R2' not in ph or 'highlight_scenario_down' in seen and 'S2' not in ph:
        problems.append('a scenario highlight needs a second level that does not exist')
    order = [seen.get(a) for a in ('show', 'draw_resistance', 'draw_support')]
    if None not in order and not order[0] < min(order[1:]):
        problems.append('show must come before drawing levels')
    n_stage = sum(L['scene'] == 'stage' for L in lines)
    n_board = sum(L['scene'] == 'board' for L in lines)
    if n_stage < spec['min_stage']:
        problems.append(f'needs at least {spec["min_stage"]} lines with scene "stage" (has {n_stage})')
    if n_board < spec['min_board']:
        problems.append(f'needs at least {spec["min_board"]} lines with scene "board" (has {n_board})')
    return problems


def expand_text(text, ph):
    display = PH.sub(lambda m: ph[m.group(1)][0] if m.group(1) in ph else m.group(0), text)
    say = PH.sub(lambda m: ph[m.group(1)][1] if m.group(1) in ph else m.group(0), text)
    return display, say


def expand(lines, data, coin_key='a'):
    """Yer tutucuları doldurur; her replik için [(ekranda, okunuş)] token listesi üretir."""
    ph = words.placeholders(data)
    for L in lines:
        L['coin'] = coin_key
        L['tokens'] = [expand_text(raw, ph) for raw in L['text'].split()]
        L['display'] = ' '.join(d for d, _ in L['tokens'])
    return lines


# ------------------------------------------------------------------ Gemini senaryosu

COMMON = """You write dialogue for "Moon or Doom", an animated stick-figure crypto commentary show (US audience).
The show describes the chart and the project; it never gives advice. Characters:
- "charlie" = Chart Charlie: {charlie_bio}
- "{sidekick}" = {sidekick_name}: {sidekick_bio}

Coin: {name} ({symbol}). Market context (for your understanding only): {context}

NUMBERS — THE MOST IMPORTANT RULE:
Never write a digit or a number word ("twenty", "hundred", "percent"...). Every number comes from a placeholder
in curly braces, which our code replaces with the verified value. Available placeholders:
{placeholders}
Use a placeholder exactly as written, e.g. "Resistance sits at {{R1}}." Do not invent other placeholders.

SCENES — every line has a "scene":
- "stage": full-screen characters (jokes, reactions)
- "chart": the candlestick chart (every chart_action line is on the chart)
- "board": an info board; set "board" to one of: {boards}
Mix the scenes as the structure says; the video must feel alive, not like a slideshow.

STRUCTURE ({n_lines} lines total, max 14 words per line):
{structure}
Hard rules:
- Never tell anyone to buy, sell or "get in". No "too late", "don't miss", no price targets, no promises
  ("guaranteed", "can't lose", "will hit"). Levels are described with conditional language only.
- No real people, no exchange names, no promotions, no invented news or facts.
- Every line is short, punchy, natural spoken English. The sidekick is funny; Charlie is calm and dry.
- emotion one of: {emotions}
- pose one of: {poses}
- jump: true only for an excited sidekick line (at most twice).

Output ONLY this JSON:
{{"lines":[{{"char":"charlie|{sidekick}","text":"...","scene":"stage|chart|board","board":"...","emotion":"...","pose":"...","chart_action":"none|show|draw_resistance|draw_support|highlight_scenario_up|highlight_scenario_down","jump":false}}]}}
"""


def build_prompt(data, spec, hook, punch, concept=None, segment=None):
    side = data['sidekick']
    ph = words.placeholders(data)
    info = data.get('info') or {}
    context = {k: data.get(k) for k in ('price', 'change_24h_pct', 'change_7d_pct', 'volume_vs_avg', 'rsi_14',
                                        'resistance_1', 'resistance_2', 'support_1', 'support_2', 'mood')}
    fields = dict(
        hook_style=HOOKS[hook], punch_style=PUNCHES[punch], why_hint=formats.why_hint(data),
        rsi_zone=formats.rsi_zone(data.get('rsi_14')), scenario_rules=formats.scenario_rules(ph),
        name=data['coin']['name'], categories=', '.join(info.get('categories') or []) or '(none)',
        description=info.get('description') or '(none: talk only about the categories)',
        concept_title=CONCEPTS[concept][1] if concept else '', concept_text=CONCEPTS[concept][2] if concept else '',
        lesson_board=CONCEPTS[concept][0] if concept else '', apply_hint=formats.apply_hint(concept, data) if concept else '',
        long_title=(segment or {}).get('long_title', ''), seg_label=(segment or {}).get('label', ''),
        move_ph='{CHANGE7D} this week' if 'CHANGE7D' in ph else '{CHANGE} today')
    structure = spec['structure'].format(**fields)
    boards = board_list(spec, CONCEPTS[concept][0] if concept else None)
    return COMMON.format(
        charlie_bio=CAST['charlie']['bio'], sidekick=side, sidekick_name=CAST[side]['name'],
        sidekick_bio=CAST[side]['bio'], name=data['coin']['name'], symbol=data['coin']['symbol'],
        context=json.dumps(context), placeholders='\n'.join(f'  {{{k}}} = {v[0]}' for k, v in ph.items()),
        boards=', '.join(boards), n_lines='-'.join(map(str, spec['lines'])), structure=structure,
        emotions=', '.join(EMOTIONS), poses=', '.join(POSES))


def write_with_gemini(data, spec, hook, punch, concept=None, segment=None, attempts=3):
    base = build_prompt(data, spec, hook, punch, concept, segment)
    lesson = CONCEPTS[concept][0] if concept else None
    feedback = ''
    for attempt in range(attempts):
        try:
            sc = parse_json(gemini(base + feedback))
        except Exception as e:
            log(f'attempt {attempt + 1} failed: {str(e)[:200]}'); continue
        problems = validate(sc, data, spec, bool(segment), lesson)
        if not problems:
            log(f'Gemini script accepted on attempt {attempt + 1}')
            return sc
        log(f'attempt {attempt + 1} rejected: {problems[:3]}')
        feedback = ('\n\nYour previous script was REJECTED for: ' + '; '.join(problems[:6]) +
                    '. Fix every issue. Remember: no digits and no number words, placeholders only.')
    return None


# ------------------------------------------------------------------ giriş noktaları

def use_gemini():
    return bool(os.environ.get('GEMINI_API_KEY')) and (os.environ.get('SCRIPT_SOURCE') or '').lower() != 'template'


def make_script(data, hist, fmt, seed=None, concept=None):
    """Tek coinli Shorts senaryosu."""
    rnd = random.Random(seed)
    spec = SHORT_FORMATS[fmt]
    last = (hist.get('videos') or [{}])[-1]
    hook = rnd.choice([h for h in HOOKS if h != last.get('hook')])
    punch = rnd.choice([p for p in PUNCHES if p != last.get('punch')])
    lesson = CONCEPTS[concept][0] if concept else None
    sc, source = None, 'template'
    if use_gemini():
        try:
            sc = write_with_gemini(data, spec, hook, punch, concept)
            source = 'gemini'
        except Exception as e:
            log(f'Gemini failed: {str(e)[:200]}')
        if sc is None:
            log('::warning::Gemini scripts failed validation, using the rule-based template')
    if sc is None:
        sc, source = formats.template(fmt, data, hook, punch, rnd, concept), 'template'
        problems = validate(sc, data, spec, False, lesson)
        if problems:
            raise RuntimeError(f'template script invalid: {problems}')
    sc.update(format=fmt, concept=concept, hook=hook, punch=punch, source=source)
    expand(sc['lines'], data)
    return sc


def make_segment(data, key, label, long_title, seed=None, kind='weekly', concept=None):
    """Uzun videonun tek coinlik bölümü. kind: weekly | majors | explained | school"""
    rnd = random.Random(seed)
    seg = {'label': label, 'long_title': long_title}
    spec = {'explained': formats.EXPLAINED_SEGMENT, 'school': formats.SCHOOL_SEGMENT}.get(kind, LONG_SEGMENT)
    lesson = CONCEPTS[concept][0] if concept else None
    sc = None
    if use_gemini():
        try:
            sc = write_with_gemini(data, spec, 'reaction', 'reality_check', concept=concept, segment=seg)
        except Exception as e:
            log(f'Gemini failed: {str(e)[:200]}')
    source = 'gemini' if sc else 'template'
    if sc is None:
        if kind == 'explained':
            sc = formats.explained_template(data, rnd, label)
        elif kind == 'school':
            sc = formats.school_segment_template(data, rnd, label, concept)
        else:
            sc = formats.segment_template(data, rnd, label, long_title)
        problems = validate(sc, data, spec, True, lesson)
        if problems:
            raise RuntimeError(f'segment template invalid: {problems}')
    expand(sc['lines'], data, key)
    return sc['lines'], source
