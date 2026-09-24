"""Moon or Doom kanal kurulumu (tekrar çalıştırılabilir; GitHub Actions 'channel' workflow'u secrets'taki token ile):
açıklama, anahtar kelimeler, ülke/dil, banner, çocuklara yönelik değil, filigran, oynatma listeleri,
ana sayfa bölümleri, yüklenmiş videoların listelere eklenmesi.

Profil fotoğrafı ve @handle API ile değiştirilemez: branding/profile.png'yi YouTube Studio > Customization'dan yükle.
"""
import json
import os
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import upload  # noqa: E402

BRAND = HERE / 'branding'
PLAYLISTS_FILE = HERE / 'playlists.json'
HIST = HERE / 'history.json'

DESCRIPTION = """Every day, the biggest crypto gainer and the biggest loser — explained by stick figures in under 60 seconds.

📈 Moon Max is sure everything is going to the moon.
📉 Bear Betty is sure everything is going to zero.
📊 Chart Charlie shows the actual chart: key support and resistance levels, RSI and what to watch next.

New Shorts 3 times a day: today's top gainer AND top loser, with levels calculated from real 4H chart data.

⚠️ Educational entertainment only. Not financial advice. Crypto is highly volatile — always do your own research. We never promote coins, exchanges or referral links.

#MoonOrDoom #crypto #altcoins"""

KEYWORDS = ('"Moon or Doom" crypto cryptocurrency bitcoin altcoins "crypto news" "top gainers" "top losers" '
            '"crypto analysis" "technical analysis" "support and resistance" "crypto shorts" "crypto today" '
            '"price analysis" "animated crypto" "stick figure"')

PLAYLISTS = {
    'gainer': ('📈 Top Gainers — To the Moon?', "Today's biggest crypto gainer, 3x a day. Moon Max is hyped, "
                                               'Chart Charlie checks the levels.'),
    'loser': ('📉 Top Losers — Going to Zero?', "Today's biggest crypto loser, 3x a day. Bear Betty is smug, "
                                               'Chart Charlie finds the support.'),
}


def step(name, fn):
    try:
        fn(); print(f'✓ {name}', flush=True)
    except Exception as e:
        print(f'✗ {name}: {str(e)[:300]}', flush=True)


def watermark(cid):
    # googleapiclient bu uç noktada 'range() arg 3 must not be zero' veriyor -> ham multipart istek
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials
    creds = Credentials(None, refresh_token=os.environ['YT_REFRESH_TOKEN'], client_id=os.environ['YT_CLIENT_ID'],
                        client_secret=os.environ['YT_CLIENT_SECRET'], token_uri='https://oauth2.googleapis.com/token')
    b = 'moonordoomBoundary'
    meta = json.dumps({'timing': {'type': 'offsetFromStart', 'offsetMs': 0},
                       'position': {'type': 'corner', 'cornerPosition': 'topRight'}})
    data = (f'--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{b}\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + (BRAND / 'watermark.png').read_bytes() + f'\r\n--{b}--\r\n'.encode()
    r = AuthorizedSession(creds).post(
        f'https://www.googleapis.com/upload/youtube/v3/watermarks/set?channelId={cid}&uploadType=multipart',
        data=data, headers={'Content-Type': f'multipart/related; boundary={b}'})
    if r.status_code >= 300:
        raise RuntimeError(f'{r.status_code} {r.text[:200]}')


def main():
    yt = upload.client()
    ch = yt.channels().list(part='id,snippet,brandingSettings,status', mine=True).execute()['items'][0]
    cid, title = ch['id'], ch['snippet']['title']
    print(f'kanal: {title} ({cid})')

    def branding():
        banner = yt.channelBanners().insert(
            media_body=MediaFileUpload(str(BRAND / 'banner.png'), mimetype='image/png')).execute()
        yt.channels().update(part='brandingSettings', body={'id': cid, 'brandingSettings': {
            'channel': {'title': title, 'description': DESCRIPTION, 'keywords': KEYWORDS, 'country': 'US',
                        'defaultLanguage': 'en'},
            'image': {'bannerExternalUrl': banner['url']}}}).execute()
    step('açıklama, anahtar kelimeler, ülke/dil, banner', branding)
    step('kanal: çocuklara yönelik değil', lambda: yt.channels().update(part='status', body={
        'id': cid, 'status': {'selfDeclaredMadeForKids': False}}).execute())
    step('filigran (abone ol)', lambda: watermark(cid))

    existing = {p['snippet']['title']: p['id'] for p in
                yt.playlists().list(part='snippet', mine=True, maxResults=50).execute().get('items', [])}
    ids = json.loads(PLAYLISTS_FILE.read_text(encoding='utf-8')) if PLAYLISTS_FILE.exists() else {}
    for key, (ptitle, pdesc) in PLAYLISTS.items():
        if key in ids:
            continue
        if ptitle in existing:
            ids[key] = existing[ptitle]; continue
        p = yt.playlists().insert(part='snippet,status', body={
            'snippet': {'title': ptitle, 'description': pdesc + '\n\nNot financial advice. #MoonOrDoom',
                        'defaultLanguage': 'en'},
            'status': {'privacyStatus': 'public'}}).execute()
        ids[key] = p['id']; print(f'✓ oynatma listesi: {ptitle}')
    PLAYLISTS_FILE.write_text(json.dumps(ids, indent=2) + '\n', encoding='utf-8')

    hist = json.loads(HIST.read_text(encoding='utf-8')) if HIST.exists() else {'videos': []}
    videos = hist.get('videos', [])
    if (os.environ.get('YT_PRIVACY') or '').lower() == 'public':  # gizli yüklenmiş eski videoları aç
        for v in videos:
            if v.get('privacy') != 'public':
                def make_public(v=v):
                    yt.videos().update(part='status', body={'id': v['video_id'], 'status': {
                        'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}}).execute()
                    v['privacy'] = 'public'
                step(f"video {v['video_id']} ({v['symbol']}) -> public", make_public)
        HIST.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding='utf-8')
    for key in PLAYLISTS:
        want = [v['video_id'] for v in videos if v.get('kind') == key]
        if not want:
            continue
        have = {i['contentDetails']['videoId'] for i in yt.playlistItems().list(
            part='contentDetails', playlistId=ids[key], maxResults=50).execute().get('items', [])}
        for vid in want:
            if vid not in have:
                step(f'video {vid} -> {key}', lambda: upload.add_to_playlist(ids[key], vid))

    if not ids.get('_sections_done'):
        sections = yt.channelSections().list(part='snippet,contentDetails', mine=True).execute().get('items', [])
        seen = {(s['snippet']['type'].lower(), tuple(s.get('contentDetails', {}).get('playlists', []))) for s in sections}
        wanted = [('recentUploads', ()), ('singlePlaylist', (ids['gainer'],)), ('singlePlaylist', (ids['loser'],))]
        for pos, (stype, pls) in enumerate(wanted):
            if (stype.lower(), pls) in seen:
                continue
            body = {'snippet': {'type': stype, 'position': pos}}
            if pls:
                body['contentDetails'] = {'playlists': list(pls)}
            step(f'ana sayfa bölümü {stype} {pls}', lambda: yt.channelSections().insert(
                part='snippet,contentDetails', body=body).execute())
        ids['_sections_done'] = True
        PLAYLISTS_FILE.write_text(json.dumps(ids, indent=2) + '\n', encoding='utf-8')
    if videos:  # YouTube'daki gerçek durum (API projesi denetimsizse videolar gizliye kilitlenir)
        items = yt.videos().list(part='status', id=','.join(v['video_id'] for v in videos[-20:])).execute()['items']
        for it in items:
            s = it['status']
            print(f"durum {it['id']}: privacy={s.get('privacyStatus')} upload={s.get('uploadStatus')} "
                  f"embeddable={s.get('embeddable')} madeForKids={s.get('madeForKids')} "
                  f"rejection={s.get('rejectionReason', '-')} failure={s.get('failureReason', '-')}")
            if s.get('embeddable') is False:
                step(f"video {it['id']} -> embeddable", lambda: yt.videos().update(part='status', body={
                    'id': it['id'], 'status': {'privacyStatus': s['privacyStatus'], 'embeddable': True,
                                               'publicStatsViewable': True, 'selfDeclaredMadeForKids': False}}).execute())
    print('\nElle yapılacak: branding/profile.png -> YouTube Studio > Customization > Branding > Picture')


if __name__ == '__main__':
    main()
