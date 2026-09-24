# StickCoin: otomatik çöp adam kripto yorum kanalı

Tasarım dokümanı: `cizgi-kripto-yorum-kanali.md`. Her şey GitHub Actions üzerinde çalışır (`.github/workflows/videos.yml`).
Karakter rig'i, Kokoro sesleri, SFX/müzik ve YouTube yükleme `çizgiKarakter` (StickStory) projesinden uyarlandı.

```
CoinGecko trend + filtre + 48 saat kuralı → borsa mumları (Binance → OKX → KuCoin → Bybit)
→ destek/direnç + RSI + EMA + hacim (kod hesaplar) → senaryo (Gemini, yer tutucularla) → doğrulama
→ Kokoro TTS (karakter başına ses) → cairo: mum grafiği + çizgi animasyonu + çöp adamlar + altyazı
→ ffmpeg → fiyat tazelik kontrolü (%3) → YouTube Shorts → Telegram bildirimi
```

Takvim: TR 10:00 / 17:00 / 23:00. Slot 1 = #1 trend, slot 2 = BTC/ETH haftalığı veya sıradaki trend / en çok yükselen,
slot 3 = en çok düşen (≤ -5%) veya sıradaki trend.

## Sayı güvenliği (Bölüm 1)
LLM hiçbir sayı yazamaz. Senaryoda `{R1}`, `{S1}`, `{CHANGE}` gibi yer tutucular kullanır ve kod bunları doğrulanmış
veriyle doldurur. Metinde rakam, sayı kelimesi ("twenty", "percent"), buy/sell, vaat ya da borsa adı geçerse senaryo
reddedilir. Gemini 3 denemede geçemezse kural tabanlı şablon kullanılır. Test: `python tests/test_validate.py`

## Kurulum (bir kez)
1. Repo secrets: `GEMINI_API_KEY` (diğer kanallarındaki anahtar olabilir)
2. YouTube kanalını bağla (tarayıcıda kripto kanalını seç):
   `python auth_setup.py --repo <kullanıcı>/<repo>` → `YT_CLIENT_ID/SECRET/REFRESH_TOKEN/CHANNEL_ID` secrets'a yazılır
3. Repo variable: `YT_PRIVACY=private` ile başla, ilk 3 gün videoları kontrol et, sonra `public` yap
4. İsteğe bağlı: `COINGECKO_API_KEY` (ücretsiz demo key), `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (her videoyu ve hatayı telefona yollar)

Ayarlar `config.yaml` içinde: günlük video sayısı, filtreler, tekrar kuralı, sesler.

## Yerel test
```
pip install -r requirements.txt
python run.py --no-upload                  # sıradaki slot, output/<id>/video.mp4
python run.py --no-upload --coin solana    # belirli coin
python run.py --no-upload --slot 3         # düşüş slotu (Bear Betty)
```
