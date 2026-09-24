"""Bölüm 14 checklist: bilinçli hatalı senaryolar reddedilmeli, şablon geçmeli.  python tests/test_validate.py"""
import copy
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stickcoin import script, words  # noqa: E402

DATA = {
    'id': 'test', 'coin': {'id': 'solana', 'symbol': 'SOL', 'name': 'Solana', 'logo': ''},
    'reason_trending': 'top_gainer_24h', 'mover_rank': 1, 'trending_rank': 1, 'price': 173.42, 'change_24h_pct': 18.2,
    'change_7d_pct': 22.4, 'volume_vs_avg': 2.4, 'rsi_14': 71.3, 'ema_50': 158.1, 'ema_200': 149.75,
    'resistance_1': 182.0, 'resistance_2': 195.4, 'support_1': 164.2, 'support_2': 151.0,
    'mood': 'bullish', 'sidekick': 'moon_max',
}


def good():
    return script.template_script(DATA, 'question', 'reality_check', random.Random(1))


def mutate(fn):
    sc = copy.deepcopy(good())
    fn(sc['lines'])
    return sc


BAD = {
    'invented price': lambda L: L[3].update(text='Resistance at $190 is the wall.'),
    'number word': lambda L: L[3].update(text='Resistance sits near one hundred ninety {R1}.'),
    'buy advice': lambda L: L[7].update(text='If it breaks {R1}, buy it, next stop {R2}.'),
    'promise': lambda L: L[1].update(text='This is guaranteed to fly, {NAME} is {RANK}.'),
    'missing disclaimer': lambda L: L[-1].update(text='Levels, not promises.'),
    'unknown placeholder': lambda L: L[3].update(text='Resistance at {R3}.'),
    'no support line': lambda L: L[4].update(chart_action='none'),
    'too long': lambda L: L[2].update(text=' '.join(['word'] * 16) + ' {VOLX}'),
    'wrong speaker': lambda L: L[0].update(char='bear_betty'),
}


def main():
    ok = True
    problems = script.validate(good(), DATA)
    print('template ->', 'OK' if not problems else problems)
    ok &= not problems
    for name, fn in BAD.items():
        problems = script.validate(mutate(fn), DATA)
        print(f'{name:20} -> {"rejected" if problems else "NOT REJECTED"}  {problems[:1]}')
        ok &= bool(problems)
    ph = words.placeholders(DATA)
    for k in ('PRICE', 'R1', 'CHANGE', 'VOLX', 'RSI', 'RANK', 'SYMBOL'):
        print(f'{k:7} {ph[k][0]:>10}  "{ph[k][1]}"')
    for p in (64250.37, 1.05, 0.4567, 0.00001234):
        print(f'{words.price_text(p):>12}  "{words.price_say(p)}"')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
