"""Video formatları: her videonun yapısı, sahne sırası ve panoları farklı olsun (YouTube "tekrarlayan içerik" riski).

Sahneler (replik başına 'scene'):
  stage  tam ekran karakter sahnesi (mekan + kamera yakınlaşması)
  chart  mum grafiği; chart_action ile destek/direnç çizilir
  board  bilgi panosu: stats | about | title | lesson_* (içeriği kod doldurur, LLM değil)

Kanalın özü değişmez: her Shorts'ta grafik gösterilir, destek ve direnç çizilir.
"""
import random

from . import words

SCENES = ['stage', 'chart', 'board']
CONCEPTS = {
    'rsi': ('lesson_rsi', 'What is RSI?', 'RSI (relative strength index): how strong recent moves were, shown as a '
                                         'gauge; high readings mean overheated, low readings mean washed out.'),
    'sr': ('lesson_sr', 'Support & resistance explained', 'support = a price where buyers showed up before; '
                                                          'resistance = a price where sellers showed up before.'),
    'volume': ('lesson_volume', 'Why volume matters', 'volume = how much actually traded; moves on big volume '
                                                      'carry more weight than moves on thin volume.'),
    'trend': ('lesson_trend', 'Moving averages in 60 seconds', 'moving averages smooth the noise; price above '
                                                               'them reads uptrend, below reads downtrend.'),
    'candles': ('lesson_candle', 'How to read candlesticks', 'each candle is four hours: the body is open to '
                                                            'close, green closed higher, red closed lower, wicks are '
                                                            'the extremes.'),
}

SHORT_FORMATS = {
    'levels': dict(
        lines=(8, 10), boards=['stats'], min_stage=2, min_board=0, scenarios=True,
        structure="""1. HOOK (line 1, sidekick, scene "stage"): {hook_style} Mention {{SYMBOL}} and {{CHANGE}}.
2. WHY (1-2 lines, charlie, scene "board", board "stats"): {why_hint}
3. CHART (scene "chart", charlie mostly, pose "pointing"): a line with chart_action "show"; a line with
   chart_action "draw_resistance" containing {{R1}}; a line with chart_action "draw_support" containing {{S1}}.
   The sidekick may interrupt once (scene "stage").
4. RSI (optional, charlie, scene "board", board "stats"): RSI is {{RSI}}, which reads "{rsi_zone}".
5. LEVELS MAP (charlie, scene "chart"):
{scenario_rules}
6. PUNCHLINE (2 lines, scene "stage"): {punch_style}
7. LAST LINE (charlie, scene "stage"): must end with exactly "Not financial advice."
"""),
    'what_is': dict(
        lines=(8, 10), boards=['about', 'stats'], min_stage=2, min_board=2, scenarios=False,
        structure="""This episode explains WHAT THE PROJECT IS, then shows its levels.
1. HOOK (line 1, sidekick, scene "stage"): {hook_style} Mention {{SYMBOL}} and {{CHANGE}}.
2. WHAT IS IT (2-3 charlie lines, scene "board", board "about"): explain in plain English what {name} is,
   using ONLY these facts (do not add anything else):
   categories: {categories}
   description: {description}
   You may use {{LAUNCHED}} / {{MCAPRANK}} if listed as placeholders.
3. The sidekick reacts to what the project is (scene "stage").
4. CHART (scene "chart", charlie, pose "pointing"): chart_action "show"; then "draw_resistance" containing
   {{R1}}; then "draw_support" containing {{S1}}.
5. PUNCHLINE (2 lines, scene "stage"): {punch_style}
6. LAST LINE (charlie, scene "stage"): must end with exactly "Not financial advice."
"""),
    'school': dict(
        lines=(8, 10), boards=None, min_stage=2, min_board=2, scenarios=False,
        structure="""This episode is CHART SCHOOL: teach ONE concept using today's coin as the example.
Concept: {concept_title}. Facts to teach: {concept_text}
1. HOOK (line 1, scene "stage"): the sidekick asks Charlie about the concept, mentioning {{SYMBOL}} and {{CHANGE}}.
2. LESSON (2-3 charlie lines, scene "board", board "{lesson_board}"): explain the concept simply. Funny analogies welcome.
3. The sidekick reacts or asks a silly follow-up (scene "stage").
4. APPLY IT (scene "chart", charlie, pose "pointing"): chart_action "show"; "draw_resistance" containing {{R1}};
   "draw_support" containing {{S1}}. Relate the concept to this chart ({apply_hint}).
5. PUNCHLINE (2 lines, scene "stage"): {punch_style}
6. LAST LINE (charlie, scene "stage"): must end with exactly "Not financial advice."
"""),
    'skit': dict(
        lines=(7, 10), boards=['stats'], min_stage=4, min_board=0, scenarios=False,
        structure="""This episode is a COMEDY SKIT on stage about how the sidekick handles today's move; the chart
appears once in the middle as the reality check.
1. HOOK (line 1, sidekick, scene "stage"): {hook_style} Mention {{SYMBOL}} and {{CHANGE}}.
2. SKIT (2-3 lines, scene "stage"): a funny situation (the sidekick's reaction, a ridiculous plan to celebrate
   or cope, Charlie deadpan). Use emotions and poses. No advice.
3. REALITY CHECK (scene "chart", charlie, pose "pointing"): chart_action "show"; "draw_resistance" containing
   {{R1}}; "draw_support" containing {{S1}}.
4. SKIT ENDING (2 lines, scene "stage"): {punch_style}
5. LAST LINE (charlie, scene "stage"): must end with exactly "Not financial advice."
"""),
}

LONG_SEGMENT = dict(
    lines=(6, 11), boards=['title', 'about', 'stats'], min_stage=1, min_board=2, scenarios=True,
    structure="""This is ONE SEGMENT of a longer video ({long_title}); the segment is about {name}.
1. INTRO (charlie, scene "board", board "title"): introduce {{NAME}} ({seg_label}) and its move ({move_ph}).
2. WHAT IS IT (1-2 charlie lines, scene "board", board "about"), ONLY from these facts:
   categories: {categories}
   description: {description}
3. REACTION (the sidekick, scene "stage"): an emotional one-liner about the move.
4. CHART (scene "chart", charlie, pose "pointing"): chart_action "show"; "draw_resistance" containing {{R1}};
   "draw_support" containing {{S1}}.
5. LEVELS MAP (charlie, scene "chart"):
{scenario_rules}
6. CLOSE (1 line, sidekick or charlie, scene "stage"): a quick joke to hand over to the next coin.
Do NOT add the disclaimer line in a segment.
""")

EXPLAINED_SEGMENT = dict(
    lines=(10, 16), boards=['title', 'about', 'stats'], min_stage=3, min_board=5, scenarios=True,
    structure="""This is ONE SEGMENT (about a minute) of "{long_title}", an evergreen explainer; the segment explains {name}.
1. INTRO (charlie, scene "board", board "title"): introduce {{NAME}} ({seg_label}).
2. WHAT IT IS (4-6 charlie lines, scene "board", board "about"): in plain English, what the project does, what
   problem it tries to solve, who uses it and what the token is for — ONLY from these facts, add nothing:
   categories: {categories}
   description: {description}
   Use a simple everyday analogy once. The sidekick may interrupt once with a naive question (scene "stage").
3. BANTER (2 lines, scene "stage"): the sidekick gives a funny take on the project; Charlie answers dryly.
4. SCORECARD (1-2 charlie lines, scene "board", board "stats"): market cap rank and today's move ({move_ph}).
5. CHART (scene "chart", charlie, pose "pointing"): chart_action "show"; "draw_resistance" containing {{R1}};
   "draw_support" containing {{S1}}.
6. LEVELS MAP (charlie, scene "chart"):
{scenario_rules}
7. CLOSE (1 line, sidekick, scene "stage"): a quick joke to hand over to the next project.
Do NOT add the disclaimer line in a segment.
""")

SCHOOL_SEGMENT = dict(
    lines=(8, 14), boards=['title', 'LESSON', 'stats'], min_stage=2, min_board=3, scenarios=True,
    structure="""This is ONE SEGMENT (about a minute) of "{long_title}", a Chart School episode about {concept_title}.
Facts to teach: {concept_text}. In this segment the concept is applied to {name}.
1. INTRO (charlie, scene "board", board "title"): introduce example {{NAME}} ({seg_label}).
2. APPLY (2-3 charlie lines, scene "board", board "{lesson_board}"): what the concept shows on this coin ({apply_hint}).
3. QUESTION (2 lines, scene "stage"): the sidekick asks a silly but real beginner question; Charlie answers simply.
4. CHART (scene "chart", charlie, pose "pointing"): chart_action "show"; "draw_resistance" containing {{R1}};
   "draw_support" containing {{S1}}; relate the concept to the chart.
5. LEVELS MAP (charlie, scene "chart"):
{scenario_rules}
6. CLOSE (1 line, sidekick or charlie, scene "stage"): hand over to the next example.
Do NOT add the disclaimer line in a segment.
""")

HOOKS = {
    'question': 'a loud, stunned QUESTION about what happened today.',
    'bold_claim': 'an absurd, over-the-top statement about how the move makes them feel.',
    'reaction': 'a pure emotional REACTION, screaming at the number.',
}
PUNCHES = {
    'reality_check': 'the sidekick says something wildly emotional; Charlie answers with one dry fact about the chart.',
    'role_reversal': 'the sidekick unexpectedly flips mood (Max gets nervous / Betty gets cheerful); Charlie reacts dryly.',
    'callback': "the sidekick repeats the hook's feeling; Charlie answers with a dry one-liner callback.",
}


def rsi_zone(r):
    if r is None:
        return 'unknown'
    return 'overbought' if r >= 70 else 'oversold' if r <= 30 else 'hot but not overbought' if r >= 60 \
        else 'weak but not oversold' if r <= 40 else 'neutral'


def trend_words(data):
    p, e50, e200 = data['price'], data.get('ema_50'), data.get('ema_200')
    if e50 is None or e200 is None:
        return 'mixed'
    if p > e50 and p > e200:
        return 'above both averages'
    if p < e50 and p < e200:
        return 'below both averages'
    return 'between the averages'


def mover_line(data):
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
    hint = 'why it is on screen: ' + mover_line(data).replace('{NAME} is', 'it is').rstrip('.')
    if data.get('trending_rank'):
        hint += ', and it is {RANK} on CoinGecko trending'
    if data.get('volume_vs_avg'):
        hint += '; volume is {VOLX} its recent average'
    return hint


def apply_hint(concept, data):
    return {'rsi': 'RSI is {RSI}, which reads "' + rsi_zone(data.get('rsi_14')) + '"',
            'sr': 'the red line is resistance, the green line is support',
            'volume': 'volume is {VOLX} its recent average' if data.get('volume_vs_avg') else 'volume bars',
            'trend': 'price is ' + trend_words(data),
            'candles': 'point at the last candles'}[concept]


def scenario_rules(ph):
    return '\n'.join([
        '   - a charlie line with chart_action "highlight_scenario_up": if it breaks {R1}, the next level on the chart is {R2}'
        if 'R2' in ph else '   - optional charlie line (chart_action "none"): what sits above {R1} on this chart',
        '   - a charlie line with chart_action "highlight_scenario_down": if it loses {S1}, the next level below is {S2}'
        if 'S2' in ph else '   - optional charlie line (chart_action "none"): what sits below {S1} on this chart'])


# ------------------------------------------------------------------ kural tabanlı şablonlar (Gemini yoksa / geçemezse)

def safe_categories(data):
    """Rakam/parantez içermeyen, kısa kategori adları (şablon metnine girecek)."""
    import re
    out = []
    for c in (data.get('info') or {}).get('categories') or []:
        c = re.sub(r'\s*\(.*?\)', '', c).strip()
        if c and not re.search(r'\d|binance|coinbase|bybit|okx|kucoin|kraken', c, re.I) and len(c) <= 28:
            out.append(c.lower())
    return out


class Lines(list):
    def say(self, char, text, emotion='neutral', pose=None, scene='stage', act='none', board=None, jump=False, opt=False):
        self.append({'char': char, 'text': text, 'emotion': emotion, 'pose': pose, 'scene': scene,
                     'chart_action': act, 'board': board, 'jump': jump, 'opt': opt})

    def trim(self, max_lines):
        """Kısa Shorts: gerekirse isteğe bağlı replikleri sondan başa doğru çıkar."""
        while len(self) > max_lines:
            idx = next((i for i in range(len(self) - 1, -1, -1) if self[i].get('opt')), None)
            if idx is None:
                break
            del self[idx]
        for L in self:
            L.pop('opt', None)
        return self


HOOK_LINES = {
    True: {'question': '{SYMBOL} up {CHANGE} in one day?! Is this real life?!',
           'bold_claim': "{SYMBOL} is up {CHANGE}! I'm naming my firstborn after it!",
           'reaction': 'WHAT?! {SYMBOL} up {CHANGE}! Somebody fuel the rocket!'},
    False: {'question': '{SYMBOL} dumped {CHANGE}. Still think crypto is the future, Charlie?',
            'bold_claim': "{SYMBOL} is down {CHANGE}. Told you. It's going to zero.",
            'reaction': 'Down {CHANGE}? {SYMBOL} holders, I have one word for you. Ouch.'},
}
PUNCH_LINES = {
    True: {'reality_check': [('Is this the part where I scream?', 'excited'), ('You already did. Twice.', 'smug')],
           'role_reversal': [('Okay, green is scary too. Hold me.', 'cry'), ('It went up. Why are you crying?', 'confused')],
           'callback': [('To the moon! Right, Charlie?', 'excited'), ('The chart says {R1} first.', 'smug')]},
    False: {'reality_check': [('Going to zero. Mark my words.', 'smug'), ('Noted. {S1} is on the chart first.', 'smug')],
            'role_reversal': [('Fine. I will watch {S1}. Quietly.', 'nervous'), ('Growth. I am proud of you.', 'happy')],
            'callback': [('Still think crypto is the future?', 'suspicious'), ('I think {S1} is the present.', 'smug')]},
}


def _hook(L, data, hook, bull):
    side = data['sidekick']
    L.say(side, HOOK_LINES[bull][hook], 'excited' if bull else 'smug', 'celebrate' if bull else 'arms_crossed',
          jump=bull)


def _chart(L, rnd, pose='pointing'):
    L.say('charlie', rnd.choice(['Here is the four-hour chart for the past week.', 'Now the chart. Past week, four-hour candles.',
                                 'Let me pull up the chart.']), 'neutral', pose, 'chart', 'show')
    L.say('charlie', rnd.choice(['First wall: resistance at {R1}.', 'Resistance sits at {R1}. Sellers showed up there before.',
                                 'Above us, the key resistance is {R1}.']), 'neutral', pose, 'chart', 'draw_resistance')
    L.say('charlie', rnd.choice(['Below, support at {S1}. Buyers defended it before.', 'Support is {S1}. That is the floor on this chart.',
                                 'The floor on this chart is {S1}.']), 'neutral', pose, 'chart', 'draw_support')


def _levels_map(L, ph):
    if 'R2' in ph:
        L.say('charlie', 'If it breaks {R1}, the next level on the chart is {R2}.', 'neutral', 'pointing', 'chart',
              'highlight_scenario_up')
    if 'S2' in ph:
        L.say('charlie', 'If it loses {S1}, the next level below is {S2}.', 'neutral', 'pointing', 'chart',
              'highlight_scenario_down')


def _punch(L, data, punch, bull):
    side = data['sidekick']
    (t1, e1), (t2, e2) = PUNCH_LINES[bull][punch]
    L.say(side, t1, e1, 'crying' if e1 == 'cry' else ('celebrate' if bull else 'arms_crossed'), jump=bull and e1 == 'excited')
    # son espri + feragatname tek satır (daha kısa video, daha iyi döngü)
    L.say('charlie', t2 + ' Not financial advice.', e2, 'shrug' if e2 == 'confused' else 'standing')


def template(fmt, data, hook, punch, rnd, concept=None):
    side = data['sidekick']
    bull = side == 'moon_max'
    ph = words.placeholders(data)
    L = Lines()
    if fmt == 'levels':
        _hook(L, data, hook, bull)
        L.say('charlie', mover_line(data), 'neutral', 'standing', 'board', board='stats')
        _chart(L, rnd)
        L.say(side, rnd.choice(['Resistance? Never heard of her.', 'Lines! I love lines!']) if bull else
              rnd.choice(['Support? Like my ex. Never there when you need it.', 'Floors are just future ceilings.']),
              'excited' if bull else 'suspicious', 'hips' if bull else 'arms_crossed', opt=True)
        if 'RSI' in ph:
            L.say('charlie', 'RSI is {RSI}. That reads ' + rsi_zone(data['rsi_14']) + ' on this chart.', 'thinking',
                  'thinking', 'board', board='stats', opt=True)
        _levels_map(L, ph)
        _punch(L, data, punch, bull)
    elif fmt == 'what_is':
        _hook(L, data, hook, bull)
        L.say('charlie', 'Before the chart: what even is {NAME}?', 'thinking', 'thinking', 'board', board='about')
        cats = safe_categories(data)
        if cats:
            L.say('charlie', 'CoinGecko files it under ' + ' and '.join(cats[:2]) + '.',
                  'neutral', 'standing', 'board', board='about')
        if 'LAUNCHED' in ph and 'MCAPRANK' in ph:
            L.say('charlie', 'It launched in {LAUNCHED} and ranks {MCAPRANK} by market cap.', 'neutral', 'standing',
                  'board', board='stats', opt=bool(cats))
        elif 'MCAPRANK' in ph:
            L.say('charlie', 'By market cap, it ranks {MCAPRANK}.', 'neutral', 'standing', 'board', board='stats',
                  opt=bool(cats))
        L.say(side, 'So it is basically a rocket with paperwork.' if bull else 'So it has a website. Impressive.',
              'excited' if bull else 'smug', 'hips' if bull else 'arms_crossed')
        _chart(L, rnd)
        _punch(L, data, punch, bull)
    elif fmt == 'school':
        board = CONCEPTS[concept][0]
        q = {'rsi': 'Charlie, {SYMBOL} moved {CHANGE}. What is this RSI thing everyone yells about?',
             'sr': '{SYMBOL} moved {CHANGE}. Charlie, what are support and resistance, really?',
             'volume': '{SYMBOL} moved {CHANGE}! Charlie, why does everyone care about volume?',
             'trend': '{SYMBOL} moved {CHANGE}. Charlie, what are those wiggly average lines?',
             'candles': '{SYMBOL} moved {CHANGE}. Charlie, how do I even read these candles?'}[concept]
        L.say(side, q, 'confused', 'shrug')
        lesson = {'rsi': ['RSI measures how strong recent moves were, like a speedometer.',
                          'High readings mean overheated. Low readings mean washed out.'],
                  'sr': ['Support is a price where buyers showed up before.',
                         'Resistance is a price where sellers showed up before.'],
                  'volume': ['Volume is how much actually traded.',
                             'A move on big volume carries more weight than a quiet one.'],
                  'trend': ['Moving averages smooth out the noise in price.',
                            'Price above them reads uptrend. Below them reads downtrend.'],
                  'candles': ['Each candle here is four hours of trading.',
                              'Green closed higher, red closed lower. Wicks show the extremes.']}[concept]
        for t in lesson:
            L.say('charlie', t, 'neutral', 'standing', 'board', board=board)
        apply = {'rsi': 'On {SYMBOL}, RSI is {RSI}. That reads ' + rsi_zone(data.get('rsi_14')) + '.' if 'RSI' in ph else None,
                 'volume': '{SYMBOL} volume is {VOLX} its recent average.' if 'VOLX' in ph else None,
                 'trend': '{SYMBOL} is trading ' + trend_words(data) + ' right now.',
                 'sr': None, 'candles': None}[concept]
        if apply:
            L.say('charlie', apply, 'thinking', 'thinking', 'board', board=board)
        L.say(side, 'I understood maybe half of that. The good half.' if bull else 'Great. Homework. My favorite.',
              'happy' if bull else 'smug', 'hips' if bull else 'arms_crossed', opt=True)
        _chart(L, rnd)
        _punch(L, data, punch, bull)
    elif fmt == 'skit':
        _hook(L, data, hook, bull)
        L.say('charlie', rnd.choice(['Sit down. It is just a chart.', 'Please stop hugging the monitor.']), 'smug', 'standing')
        L.say(side, 'I am throwing a party. The theme is green candles.' if bull else
              'I am throwing a funeral. The theme is red candles.', 'excited' if bull else 'sad',
              'celebrate' if bull else 'arms_crossed', jump=bull)
        L.say('charlie', 'Before the party planning, look at this.', 'neutral', 'pointing', 'stage')
        _chart(L, rnd)
        _punch(L, data, punch, bull)
    return {'lines': L.trim(SHORT_FORMATS[fmt]['lines'][1])}


def segment_template(data, rnd, label, long_title):
    """Uzun video segmenti (bir coin)."""
    side = data['sidekick']
    bull = side == 'moon_max'
    ph = words.placeholders(data)
    move = '{CHANGE7D} this week' if 'CHANGE7D' in ph else '{CHANGE} today'
    L = Lines()
    L.say('charlie', f'Next up: {{NAME}}, {label}, {"up" if bull else "down"} {move}.', 'neutral', 'standing', 'board',
          board='title')
    cats = safe_categories(data)
    if cats:
        L.say('charlie', 'CoinGecko files it under ' + ' and '.join(cats[:2]) + '.',
              'neutral', 'standing', 'board', board='about')
    L.say('charlie', 'By market cap it ranks {MCAPRANK}. Here is its scorecard.' if 'MCAPRANK' in ph else
          'Here is its scorecard for the week.', 'neutral', 'standing', 'board', board='stats')
    L.say(side, rnd.choice(['My heart cannot take this much green!', 'I am framing this chart!']) if bull else
          rnd.choice(['I brought tissues. For them, not me.', 'Called it. I always call it.']),
          'excited' if bull else 'smug', 'celebrate' if bull else 'arms_crossed')
    _chart(L, rnd)
    _levels_map(L, ph)
    L.say(side, rnd.choice(['Next coin! Faster!', 'Okay, okay. Who is next?']) if bull else
          rnd.choice(['Next victim, please.', 'Moving on. Slowly. Dramatically.']), 'happy' if bull else 'smug',
          'hips' if bull else 'arms_crossed')
    return {'lines': L.trim(99)}


LESSONS = {
    'rsi': ['RSI measures how strong recent moves were, like a speedometer.',
            'High readings mean overheated. Low readings mean washed out.'],
    'sr': ['Support is a price where buyers showed up before.',
           'Resistance is a price where sellers showed up before.'],
    'volume': ['Volume is how much actually traded.', 'A move on big volume carries more weight than a quiet one.'],
    'trend': ['Moving averages smooth out the noise in price.',
              'Price above them reads uptrend. Below them reads downtrend.'],
    'candles': ['Each candle here is four hours of trading.',
                'Green closed higher, red closed lower. Wicks show the extremes.'],
}


# Chart School uzun bölüm girişi: sabit, doğrulanmış ders metni (rakam yok, tavsiye yok)
LESSONS_LONG = {
    'rsi': ['RSI stands for relative strength index.',
            'It looks at recent candles and asks one question: how strong were the up moves compared to the down moves?',
            'The answer is shown as a gauge, from washed out on the left to overheated on the right.',
            'A high reading means buyers have been pushing hard. A low reading means sellers have.',
            'It does not tell you what happens next. It tells you how stretched the move already is.',
            'Traders usually read it together with support and resistance, never alone.'],
    'sr': ['Support is a price area where buyers stepped in before and stopped a fall.',
           'Resistance is a price area where sellers stepped in before and stopped a rise.',
           'Think of a ball bouncing between a floor and a ceiling.',
           'The more times price touched a level, the more traders pay attention to it.',
           'When a ceiling breaks, it can turn into a floor, and the other way around.',
           'Levels are zones, not laser lines. Price often pokes through a little.'],
    'volume': ['Volume is simply how much of a coin actually changed hands.',
               'Price tells you where it went. Volume tells you how many people agreed.',
               'A big move on tiny volume is like a loud party with three guests.',
               'A big move on heavy volume means a lot of traders took part.',
               'That is why chart readers compare today with the recent average.',
               'Volume bars sit under the chart, green for up candles and red for down ones.'],
    'trend': ['A moving average is the average price over the last stretch of candles.',
              'It moves forward with every new candle, which smooths out the noise.',
              'A fast average reacts quickly. A slow average reacts calmly.',
              'Price above both usually reads as an uptrend. Below both reads as a downtrend.',
              'When the fast one crosses the slow one, traders call it a crossover.',
              'Averages describe the trend that already happened. They lag by design.'],
    'candles': ['Every candle is a small story about one chunk of time. Here, four hours.',
                'The thick body runs from where price opened to where it closed.',
                'Green means it closed higher than it opened. Red means it closed lower.',
                'The thin wicks show the highest and lowest prices during those hours.',
                'Long wicks mean price went somewhere and got pushed back.',
                'Read a few candles together and you start to see who is in control.'],
}


def apply_line(concept, data, ph):
    return {'rsi': 'On {SYMBOL}, RSI is {RSI}. That reads ' + rsi_zone(data.get('rsi_14')) + '.' if 'RSI' in ph else None,
            'volume': '{SYMBOL} volume is {VOLX} its recent average.' if 'VOLX' in ph else None,
            'trend': '{SYMBOL} is trading ' + trend_words(data) + ' right now.',
            'sr': 'On {SYMBOL}, the red line is resistance, the green line is support.',
            'candles': 'On {SYMBOL}, look at the size of the last few candle bodies.'}[concept]


def explained_template(data, rnd, label):
    side = data['sidekick']
    bull = side == 'moon_max'
    ph = words.placeholders(data)
    L = Lines()
    L.say('charlie', f'Project up next: {{NAME}}, {label}.', 'neutral', 'standing', 'board', board='title')
    L.say('charlie', 'So what actually is {NAME}?', 'thinking', 'thinking', 'board', board='about')
    cats = safe_categories(data)
    L.say('charlie', ('CoinGecko files it under ' + ' and '.join(cats[:2]) + '.') if cats else
          'Its official listing keeps the description short.', 'neutral', 'standing', 'board', board='about')
    if 'LAUNCHED' in ph:
        L.say('charlie', 'It has been around since {LAUNCHED}.', 'neutral', 'standing', 'board', board='about')
    L.say(side, rnd.choice(['Does it come with a rocket? Asking for me.', 'Can I wear it?']) if bull else
          rnd.choice(['Does it come with a refund policy?', 'Is there a version that only goes up?']),
          'confused' if bull else 'suspicious', 'shrug' if bull else 'arms_crossed')
    L.say('charlie', rnd.choice(['No. It comes with a chart.', 'Sadly, no. But it has a chart.']), 'smug', 'standing')
    L.say('charlie', 'By market cap it ranks {MCAPRANK}.' if 'MCAPRANK' in ph else 'Here is its scorecard.',
          'neutral', 'standing', 'board', board='stats')
    L.say('charlie', f'Today it is {"up" if data["change_24h_pct"] >= 0 else "down"} {{CHANGE}}.', 'neutral',
          'standing', 'board', board='stats')
    _chart(L, rnd)
    _levels_map(L, ph)
    L.say(side, rnd.choice(['Next project! I have more questions!', 'Okay, who is next?']) if bull else
          rnd.choice(['Next one. Impress me.', 'Moving on. Slowly.']), 'happy' if bull else 'smug',
          'hips' if bull else 'arms_crossed')
    return {'lines': L.trim(99)}


def school_segment_template(data, rnd, label, concept):
    side = data['sidekick']
    bull = side == 'moon_max'
    ph = words.placeholders(data)
    board = CONCEPTS[concept][0]
    L = Lines()
    L.say('charlie', f'Example time: {{NAME}}, {label}.', 'neutral', 'standing', 'board', board='title')
    L.say('charlie', apply_line(concept, data, ph) or 'Let us read this one together.', 'thinking', 'thinking',
          'board', board=board)
    L.say('charlie', LESSONS[concept][1], 'neutral', 'standing', 'board', board=board)
    L.say(side, rnd.choice(['I get it! I think. Maybe.', 'Wait, I actually understood that!']) if bull else
          rnd.choice(['Fine. That was mildly useful.', 'I hate that this makes sense.']),
          'happy' if bull else 'smug', 'hips' if bull else 'arms_crossed')
    L.say('charlie', rnd.choice(['That is the whole trick. Now watch it on the chart.',
                                 'Good. Now the real chart.']), 'smug', 'standing')
    _chart(L, rnd)
    _levels_map(L, ph)
    L.say(side, rnd.choice(['Next example, professor!', 'More! Give me more!']) if bull else
          rnd.choice(['Next patient, please.', 'Go on. I am listening. Barely.']), 'excited' if bull else 'smug',
          'hips' if bull else 'arms_crossed')
    return {'lines': L.trim(99)}


def pick_format(hist, rnd, data, avoid=()):
    """Son 2 videonun ve bu çalıştırmada kullanılanların formatı tekrarlanmaz."""
    recent = [v.get('format') for v in hist.get('videos', []) if v.get('kind') in ('gainer', 'loser')][-2:]
    options = [f for f in SHORT_FORMATS if f not in recent and f not in avoid] or \
              [f for f in SHORT_FORMATS if f not in avoid]
    if not (data.get('info') or {}).get('categories') and not (data.get('info') or {}).get('description'):
        options = [f for f in options if f != 'what_is'] or ['levels']
    # karakter komedisi en iyi performansı veriyor (Dex & Friends verisi) -> skit daha sık
    weights = [FORMAT_WEIGHTS.get(f, 1) for f in options]
    return rnd.choices(options, weights)[0]


FORMAT_WEIGHTS = {'skit': 3, 'levels': 1, 'what_is': 2, 'school': 2}  # levels = seviye haritası, sinyal gibi algılanmasın diye seyrek


def pick_concept(hist, rnd, data):
    recent = [v.get('concept') for v in hist.get('videos', []) if v.get('concept')][-3:]
    options = [c for c in CONCEPTS if c not in recent]
    if data.get('volume_vs_avg') is None:
        options = [c for c in options if c != 'volume']
    if data.get('rsi_14') is None:
        options = [c for c in options if c != 'rsi']
    return rnd.choice(options or ['sr'])
