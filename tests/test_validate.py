"""Bilinçli hatalı senaryolar reddedilmeli; her formatın şablonu (yükseliş + düşüş) geçmeli.  python tests/test_validate.py"""
import copy
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stickcoin import formats, script, words  # noqa: E402
from stickcoin.formats import CONCEPTS, LONG_SEGMENT, SHORT_FORMATS  # noqa: E402

CANDLES = [[0, 100 + i, 102 + i, 99 + i, 101 + i, 1000 + 10 * i] for i in range(42)]
BULL = {
    'id': 'test', 'coin': {'id': 'solana', 'symbol': 'SOL', 'name': 'Solana', 'logo': '', 'market_cap_rank': 6},
    'reason_trending': 'top_gainer_24h', 'mover_rank': 1, 'trending_rank': 1, 'price': 173.42, 'change_24h_pct': 18.2,
    'change_7d_pct': 22.4, 'volume_vs_avg': 2.4, 'rsi_14': 71.3, 'ema_50': 158.1, 'ema_200': 149.75,
    'resistance_1': 182.0, 'resistance_2': 195.4, 'support_1': 164.2, 'support_2': 151.0,
    'mood': 'bullish', 'sidekick': 'moon_max', 'chart': {'candles': CANDLES},
    'info': {'categories': ['Layer 1 (L1)', 'Smart Contract Platform', 'Solana Ecosystem'],
             'description': 'Solana is a blockchain.', 'launched': 2020},
}
BEAR = dict(copy.deepcopy(BULL), change_24h_pct=-9.1, change_7d_pct=-14.0, mood='bearish', sidekick='bear_betty',
            reason_trending='top_loser_24h', resistance_2=None, info={})


def levels_script():
    return formats.template('levels', BULL, 'question', 'reality_check', random.Random(1))


def mutate(fn):
    sc = copy.deepcopy(levels_script())
    fn(sc['lines'])
    return sc


def find(lines, act):
    return next(L for L in lines if L['chart_action'] == act)


BAD = {
    'invented price': lambda L: find(L, 'draw_resistance').update(text='Resistance at $190 is the wall.'),
    'number word': lambda L: find(L, 'draw_resistance').update(text='Resistance sits near one hundred ninety {R1}.'),
    'buy advice': lambda L: find(L, 'highlight_scenario_up').update(text='If it breaks {R1}, buy it, next {R2}.'),
    'FOMO': lambda L: L[0].update(text='{SYMBOL} up {CHANGE}! Is it too late?!'),
    'promise': lambda L: L[1].update(text='This is guaranteed to fly, {NAME} is {RANK}.'),
    'missing disclaimer': lambda L: L[-1].update(text='Levels, not promises.'),
    'unknown placeholder': lambda L: find(L, 'draw_resistance').update(text='Resistance at {R3}.'),
    'no support line': lambda L: find(L, 'draw_support').update(chart_action='none'),
    'too long': lambda L: L[2].update(text=' '.join(['word'] * 16) + ' {VOLX}'),
    'wrong speaker': lambda L: L[0].update(char='bear_betty'),
}


def main():
    ok = True
    for data in (BULL, BEAR):
        for fmt, spec in SHORT_FORMATS.items():
            concepts = list(CONCEPTS) if fmt == 'school' else [None]
            for c in concepts:
                sc = formats.template(fmt, data, 'question', 'callback', random.Random(2), c)
                problems = script.validate(sc, data, spec, False, CONCEPTS[c][0] if c else None)
                print(f"template {data['mood']:8} {fmt:8} {c or '':8} -> {'OK' if not problems else problems}  ({len(sc['lines'])} lines)")
                ok &= not problems
        seg = formats.segment_template(data, random.Random(3), "this week's top gainer", 'Weekly')
        problems = script.validate(seg, data, LONG_SEGMENT, True)
        print(f"segment  {data['mood']:8} -> {'OK' if not problems else problems}")
        ok &= not problems
    for name, fn in BAD.items():
        problems = script.validate(mutate(fn), BULL, SHORT_FORMATS['levels'])
        print(f'{name:20} -> {"rejected" if problems else "NOT REJECTED"}  {problems[:1]}')
        ok &= bool(problems)
    ph = words.placeholders(BULL)
    for k in ('PRICE', 'R1', 'CHANGE', 'VOLX', 'RSI', 'RANK', 'SYMBOL', 'MCAPRANK', 'LAUNCHED'):
        print(f'{k:9} {ph[k][0]:>10}  "{ph[k][1]}"')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
