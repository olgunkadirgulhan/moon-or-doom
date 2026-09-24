# Moon or Doom: otomatik çöp adam kripto kanalı

Kanal: **Moon or Doom** (YouTube). Tasarım dokümanı: `cizgi-kripto-yorum-kanali.md`. Her şey GitHub Actions üzerinde
çalışır (`.github/workflows/videos.yml`). Karakter rig'i, Kokoro sesleri, SFX/müzik ve YouTube yükleme `çizgiKarakter`
(StickStory) projesinden uyarlandı.

```
CoinGecko + filtre + 48 saat kuralı → borsa mumları (Binance → OKX → KuCoin → Bybit) + proje bilgisi
→ destek/direnç + RSI + EMA + hacim (kod hesaplar) → senaryo (Gemini, formatın yapısı + yer tutucular) → doğrulama
→ Kokoro TTS → cairo: sahne / grafik / pano + çöp adamlar + altyazı + beğen-abone kartı
→ ffmpeg → fiyat tazelik kontrolü (%3) → YouTube → oynatma listesi
```

## Takvim
| Ne | Ne zaman (TR) | İçerik |
|---|---|---|
| Shorts x2 | ~16:00 | günün en çok yükseleni + 5 dk sonra en çok düşeni |
| Shorts x2 | ~23:00 | aynı (48 saat kuralıyla sıradaki coinler) |
| Uzun video | Salı ~18:30 | **Moon or Doom Explained**: trend olan 3 proje ne işe yarıyor + grafikleri, 16:9 |
| Uzun video | Cuma ~18:30 | **Chart School**: tek kavram (RSI, destek/direnç, hacim...) + 3 gerçek grafik örneği |

Kardeş kanal **Whale Market Pulse** (crypto-shorts-factory) Pazar/Çarşamba haftalık özet yapar; Moon or Doom o konuyu
ve günleri kullanmaz, ayrıca Whale'in son 36 saatte işlediği coinleri (herkese açık RSS) atlar. `weekly` ve `majors`
uzun videoları kodda duruyor ama takvimde yok (elle: `--long weekly`).

Her yüklemeden sonra kanal adına etkileşim sorusu soran bir yorum atılır (`youtube.force-ssl` izni gerekir; eski
token'da yoksa atlanır, `python auth_setup.py --repo ...` ile yeniden bağlanınca açılır).

## Tekrarlayan içerik koruması (para kazanma)
Her Shorts farklı formatta çıkar, son 2 videonun formatı tekrarlanmaz:
- **levels**: destek/direnç haritası + istatistik kartı
- **what_is**: projenin ne olduğu (CoinGecko açıklaması + kategoriler), sonra seviyeler
- **school**: Chart School, günün coiniyle tek kavram (RSI, destek/direnç, hacim, ortalamalar, mumlar)
- **skit**: tam ekran komedi sahnesi, grafik ortada "gerçeklik kontrolü" olarak

Sahneler: `stage` (tam ekran karakterler, kamera yakınlaşması), `chart` (mum grafiği), `board` (bilgi/ders panosu).

## Sayı güvenliği
LLM hiçbir sayı yazamaz; `{R1}`, `{S1}`, `{CHANGE}` gibi yer tutucular kullanır, kod doğrulanmış veriyle doldurur.
Rakam, sayı kelimesi, buy/sell, "too late" gibi FOMO ifadeleri, vaat ya da borsa adı geçerse senaryo reddedilir.
Gemini 3 denemede geçemezse kural tabanlı şablon kullanılır. Test: `python tests/test_validate.py`

## Kota
Google Cloud projesi `moonorrdoom` (yalnız bu kanal): günlük 10.000 birim, yükleme başı 1.600 → günde 4 Shorts +
uzun video günü 1 = en fazla 8.000 birim.

## Kurulum (yapıldı)
- Secrets: `GEMINI_API_KEY`, `YT_CLIENT_ID/SECRET/REFRESH_TOKEN/CHANNEL_ID` (`python auth_setup.py --repo ...`)
- Variable: `YT_PRIVACY=public`
- Kanal: `channel` workflow'u → banner, açıklama, filigran, oynatma listeleri, ana sayfa bölümleri
- Elle: profil resmi (`branding/profile.png`) ve handle, YouTube Studio'dan

## Yerel test
```
pip install -r requirements.txt
python run.py --no-upload                              # yükselen + düşen, otomatik format
python run.py --no-upload --only loser --format school
python run.py --no-upload --long weekly                # 16:9 uzun video
```
