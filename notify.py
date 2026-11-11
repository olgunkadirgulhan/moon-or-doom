"""İsteğe bağlı Telegram bildirimi (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID). Yoksa sessizce atlanır."""
import os

import requests


def configured():
    return bool(os.environ.get('TELEGRAM_BOT_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'))


def _api(method, **kw):
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"
    r = requests.post(url, timeout=120, **kw)
    r.raise_for_status()


def message(text):
    if not configured():
        return
    try:
        _api('sendMessage', data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': text[:4000],
                                  'disable_web_page_preview': True})
    except Exception as e:
        print(f'[notify] telegram failed: {e}', flush=True)


# 2026-11-11: dosya yok, sadece yazı
def video(path, caption):
    message(caption)


def document(path, caption):
    message(caption)

def copyable(label, text):
    return
    """Başlık + dokununca kopyalanan kutu (Telegram'da <pre> bloğu)."""
    if not configured():
        return
    esc = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    try:
        _api('sendMessage', data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'parse_mode': 'HTML',
                                  'text': f'{label}\n<pre>{esc[:3800]}</pre>', 'disable_web_page_preview': True})
    except Exception as e:
        print(f'[notify] telegram failed: {e}', flush=True)
        message(f'{label}\n\n{text}')
