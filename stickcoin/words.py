"""Sayıların ekrandaki ve sesli okunan hali. TTS'e rakam verilmez: "$182.40" -> "one hundred eighty-two dollars and forty cents"."""
import math

ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
        'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']


def int_words(n):
    n = int(n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ('-' + ONES[n % 10] if n % 10 else '')
    if n < 1000:
        return ONES[n // 100] + ' hundred' + (' ' + int_words(n % 100) if n % 100 else '')
    for size, name in ((10 ** 12, 'trillion'), (10 ** 9, 'billion'), (10 ** 6, 'million'), (1000, 'thousand')):
        if n >= size:
            return int_words(n // size) + ' ' + name + (' ' + int_words(n % size) if n % size else '')
    return str(n)


def digits_words(s):
    return ' '.join(ONES[int(c)] for c in s)


def dec_words(x, nd=1):
    s = f'{abs(x):.{nd}f}'
    whole, frac = s.split('.') if '.' in s else (s, '')
    frac = frac.rstrip('0')
    return int_words(int(whole)) + (' point ' + digits_words(frac) if frac else '')


def sig_decimals(p):
    """1 doların altında 4 anlamlı basamak için ondalık sayısı."""
    return max(2, 3 - int(math.floor(math.log10(abs(p)))))


def price_text(p):
    if p >= 1000:
        return f'${p:,.0f}'
    if p >= 1:
        return f'${p:,.2f}'
    return f'${p:.{sig_decimals(p)}f}'


def price_say(p):
    if p >= 1000:
        return int_words(round(p)) + ' dollars'
    if p >= 1:
        dollars, cents = int(p), int(round((p - int(p)) * 100))
        if cents == 100:
            dollars, cents = dollars + 1, 0
        out = int_words(dollars) + (' dollar' if dollars == 1 else ' dollars')
        return out + (' and ' + int_words(cents) + ' cents' if cents else '')
    if p >= 0.01:
        return dec_words(p * 100, max(0, sig_decimals(p) - 2)) + ' cents'
    s = f'{p:.{sig_decimals(p)}f}'.split('.')[1].rstrip('0')
    return 'zero point ' + digits_words(s) + ' dollars'


def year_say(y):
    y = int(y)
    if 2000 <= y < 2010:
        return 'two thousand' + (' ' + ONES[y - 2000] if y > 2000 else '')
    return int_words(y // 100) + ' ' + (int_words(y % 100) if y % 100 >= 10 else 'oh ' + ONES[y % 100])


def pct_text(x):
    return f'{abs(x):.1f}%'


def pct_say(x):
    return dec_words(x, 1) + ' percent'


def placeholders(data):
    """Senaryoda kullanılabilecek yer tutucular: {KEY: (ekranda, okunuş)}. None olan değer yer tutucu olamaz."""
    c = data['coin']
    sym = c['symbol']
    # sesli harfi olmayan ticker harf harf okunur (BTC -> "B T C"), diğerleri kelime gibi (SOL, NEAR)
    sym_say = ' '.join(sym) if not any(ch in 'AEIOU' for ch in sym.upper()) else sym.capitalize()
    ph = {'SYMBOL': ('$' + sym, sym_say), 'NAME': (c['name'], c['name'])}
    for key, field in (('PRICE', 'price'), ('R1', 'resistance_1'), ('R2', 'resistance_2'), ('S1', 'support_1'),
                       ('S2', 'support_2')):  # EMA sayıları verilmez: bağlamsız okununca anlamsız; trend sözle anlatılır
        if data.get(field) is not None:
            ph[key] = (price_text(data[field]), price_say(data[field]))
    ph['CHANGE'] = (pct_text(data['change_24h_pct']), pct_say(data['change_24h_pct']))
    if data.get('change_7d_pct') is not None:
        ph['CHANGE7D'] = (pct_text(data['change_7d_pct']), pct_say(data['change_7d_pct']))
    if data.get('rsi_14') is not None:
        ph['RSI'] = (f"{data['rsi_14']:.0f}", int_words(round(data['rsi_14'])))
    if data.get('volume_vs_avg') is not None:
        ph['VOLX'] = (f"{data['volume_vs_avg']:.1f}x", dec_words(data['volume_vs_avg'], 1) + ' times')
    if data.get('trending_rank'):
        ph['RANK'] = (f"#{data['trending_rank']}", 'number ' + int_words(data['trending_rank']))
    if c.get('market_cap_rank'):
        ph['MCAPRANK'] = (f"#{c['market_cap_rank']}", 'number ' + int_words(c['market_cap_rank']))
    launched = (data.get('info') or {}).get('launched')
    if launched:
        ph['LAUNCHED'] = (str(launched), year_say(launched))
    return ph
