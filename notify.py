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


def video(path, caption):
    if not configured():
        return
    try:
        if os.path.getsize(path) > 49 * 1024 * 1024:
            return message(caption)
        with open(path, 'rb') as f:
            _api('sendVideo', data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'caption': caption[:1000]},
                 files={'video': f})
    except Exception as e:
        print(f'[notify] telegram video failed: {e}', flush=True)


def document(path, caption):
    """Orijinal dosya, sıkıştırmasız (TikTok/Instagram'a kaliteli yüklemek için); 50 MB üstü metne düşer."""
    if not configured():
        return
    try:
        if os.path.getsize(path) > 49 * 1024 * 1024:
            return message(caption)
        with open(path, 'rb') as f:
            _api('sendDocument', data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'caption': caption[:1000]},
                 files={'document': (os.path.basename(str(path)), f, 'video/mp4')})
    except Exception as e:
        print(f'[notify] telegram document failed: {e}', flush=True)
        message(caption)


def copyable(label, text):
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
