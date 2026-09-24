# Çöp Adam Kripto Yorum Kanalı — Üretim Sistemi

> Format: Renkli çöp adamlar gündemde en trend olan coinleri yorumlar. Ekranda grafik gösterilir, destek ve direnç seviyeleri söylenir.
> Süre: **50 sn** · Oran: **9:16 (1080×1920)** · Dil: İngilizce (ABD kitlesi)
> Altyapı: Mevcut n8n + Ollama + Remotion hattı. Veri kaynağı olarak kripto API'leri eklenir.

---

## 1. Temel Kural: Sayıları LLM Üretmez

Fiyat, yüzde değişim, destek, direnç ve hacim gibi **her sayı koddan hesaplanır**. LLM yalnızca bu sayıları konuşma diline çevirir. Senaryoda JSON'da olmayan bir sayı geçerse video reddedilir (bkz. Bölüm 8). Kripto kanalında tek bir yanlış fiyat kanalın güvenilirliğini bitirir.

---

## 2. Takvim

| Slot | TR saati | İçerik |
|---|---|---|
| 1 | 10:00 | #1 trend coin |
| 2 | 17:00 | #2 trend coin (veya günün en çok yükseleni) |
| 3 | 23:00 | #3 trend coin (veya günün en çok düşeni) |

- Aynı coin 48 saat içinde tekrar işlenmez. İstisna: son videodan beri %15'ten fazla hareket ettiyse.
- BTC ve ETH, trend listesinde olmasa bile haftada 1'er kez işlenir.
- Günlük video sayısı `config.yaml` içinde `daily_videos: 3` ile değiştirilebilir.

---

## 3. Karakterler

İki karakter karşılıklı konuşur. Tartışma formatı izleyiciyi videoda daha uzun tutar.

| Karakter | Renk | Aksesuar | Rol | Ses |
|---|---|---|---|---|
| **Chart Charlie** | Mavi gömlek | Gözlük, elinde işaretçi çubuk | Analist. Grafiği gösterir, seviyeleri söyler. | Sakin, net, orta yaş erkek |
| **Moon Max** | Yeşil hoodie | Roket rozeti | Aşırı iyimser yatırımcı. "To the moon!" diye bağırır. | Genç, heyecanlı |
| **Bear Betty** | Kırmızı ceket | Kalın kaşlar, kollar hep kavuşmuş | Şüpheci. "It's going to zero" der. | Kuru, alaycı kadın sesi |

**Karakter seçimi:** Charlie her videoda yer alır. Coin son 24 saatte yükseldiyse yanına Moon Max, düştüyse Bear Betty gelir. İkinci karakter, analistin gerçekçi yorumuna duygusal bir kontrast oluşturur.

**Pozlar:** `pointing_chart, arms_crossed, jumping, facepalm, shocked, crying, thinking, shrug`
**Ağız şekilleri:** `closed · ai · e · o · u · scream` (lip-sync için Rhubarb)

---

## 4. 50 Saniyelik Video Yapısı

```
0–3 sn    HOOK        Max/Betty bağırır + dev coin logosu + % değişim
                      "SOL just pumped 18%! Is it too late?!"
3–10 sn   NEDEN       Charlie: Trend olma sebebi (hacim artışı, sıralama, % hareket)
10–30 sn  GRAFİK      Ekranın üst 2/3'ünde mum grafiği belirir.
                      Karakterler alt 1/3'te durur. Charlie çubukla gösterir.
                      Direnç çizgisi (kırmızı) → "Resistance at $182"
                      Destek çizgisi (yeşil)  → "Support at $164"
30–42 sn  SENARYOLAR  "If it breaks $182 → next level $195"
                      "If it loses $164 → watch $151"
42–48 sn  PUNCHLINE   Max/Betty duygusal tepki verir, Charlie kuru espriyle kapatır
48–50 sn  KAPANIŞ     "Not financial advice." + loop karesi
```

**Ekran düzeni (9:16):**
```
┌─────────────────────┐
│  $SOL  +18.2% 24h   │ ← üst bant: logo, fiyat, değişim
├─────────────────────┤
│                     │
│   MUM GRAFİĞİ       │ ← 4 saatlik mumlar, son 7 gün
│   ─── R $182 ───    │   kırmızı kesikli çizgi
│   ─── S $164 ───    │   yeşil kesikli çizgi
│                     │
├─────────────────────┤
│  🧍Charlie   🧍Max   │ ← karakterler + konuşma balonu
│  [altyazı]          │
└─────────────────────┘
```

---

## 5. Veri Kaynakları

| Veri | Kaynak | Endpoint |
|---|---|---|
| Trend coinler | CoinGecko (ücretsiz) | `GET /api/v3/search/trending` |
| Fiyat, 24s değişim, hacim, piyasa değeri | CoinGecko | `GET /api/v3/coins/markets?vs_currency=usd&ids=...` |
| OHLCV mumları | Binance | `GET /api/v3/klines?symbol=SOLUSDT&interval=4h&limit=200` |
| Yedek OHLCV | Bybit / OKX / CoinGecko `/coins/{id}/ohlc` | Coin Binance'te listeli değilse |
| Günün en çok yükselen/düşenleri | CoinGecko markets, `price_change_percentage_24h` ile sıralama | — |

**Coin seçim filtresi:** Aşağıdaki koşulları sağlamayan coin işlenmez.
- Piyasa değeri 50M dolardan büyük
- 24 saatlik hacim 10M dolardan büyük
- En az 1 büyük borsada USDT paritesi olmalı
- Stablecoin ve wrapped token (USDT, USDC, WBTC vb.) listeden çıkarılır

Bu filtre, pump & dump yapılan mikro coinleri tanıtmayı önler. Hem hukuki hem de itibar riski taşırlar.

---

## 6. Destek ve Direnç Hesaplama (Python)

```python
import numpy as np
import pandas as pd

def swing_points(df, window=5):
    """Yerel tepe ve dipleri bulur."""
    highs, lows = [], []
    for i in range(window, len(df) - window):
        seg = df.iloc[i - window:i + window + 1]
        if df['high'].iloc[i] == seg['high'].max():
            highs.append(df['high'].iloc[i])
        if df['low'].iloc[i] == seg['low'].min():
            lows.append(df['low'].iloc[i])
    return highs, lows

def cluster_levels(levels, tolerance_pct=1.0):
    """Birbirine %1'den yakın seviyeleri tek seviyede birleştirir; dokunuş sayısını tutar."""
    levels = sorted(levels)
    clusters = []
    for lvl in levels:
        if clusters and abs(lvl - clusters[-1]['price']) / clusters[-1]['price'] * 100 < tolerance_pct:
            c = clusters[-1]
            c['touches'] += 1
            c['price'] = (c['price'] * (c['touches'] - 1) + lvl) / c['touches']
        else:
            clusters.append({'price': lvl, 'touches': 1})
    return clusters

def support_resistance(df):
    price = df['close'].iloc[-1]
    highs, lows = swing_points(df)
    levels = cluster_levels(highs + lows)
    # Güç sıralaması: dokunuş sayısı, eşitlikte fiyata yakınlık
    res = sorted([l for l in levels if l['price'] > price],
                 key=lambda l: (-l['touches'], l['price'] - price))
    sup = sorted([l for l in levels if l['price'] < price],
                 key=lambda l: (-l['touches'], price - l['price']))
    # Ana seviye = en yakın güçlü seviye; ikincil = bir sonraki
    r = sorted(res[:3], key=lambda l: l['price'])
    s = sorted(sup[:3], key=lambda l: -l['price'])
    return {
        'price': round(price, 6),
        'resistance_1': r[0]['price'] if r else None,
        'resistance_2': r[1]['price'] if len(r) > 1 else None,
        'support_1': s[0]['price'] if s else None,
        'support_2': s[1]['price'] if len(s) > 1 else None,
    }

def extras(df):
    close = df['close']
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss)
    return {
        'rsi_14': round(rsi.iloc[-1], 1),
        'ema_50': round(close.ewm(span=50).mean().iloc[-1], 6),
        'ema_200': round(close.ewm(span=200).mean().iloc[-1], 6),
        'volume_vs_avg': round(df['volume'].iloc[-6:].sum() / df['volume'].iloc[-60:-6].mean() / 6, 2),
    }
```

**Seviye yuvarlama kuralı:** Fiyat 1 dolardan büyükse 2 anlamlı ondalık, küçükse 4–6 ondalık kullanılır. Senaryoda söylenecek hali ayrıca `spoken` alanına yazılır (ör. `"$0.00001234"` → `"about one point two three hundred-thousandths of a cent"` yerine `"0.0000123"`).

**Doğrulama:** Seviye mevcut fiyata %0.5'ten yakın veya %25'ten uzaksa kullanılmaz; bir sonraki seviyeye geçilir.

---

## 7. Veri JSON'u (Senaryo Girdisi)

```json
{
  "id": "crypto_2026-09-25_01",
  "coin": {"id": "solana", "symbol": "SOL", "name": "Solana", "logo": "assets/logos/sol.png"},
  "reason_trending": "coingecko_trending_rank_1",
  "price": 173.42,
  "change_24h_pct": 18.2,
  "volume_24h_usd": 6120000000,
  "volume_vs_avg": 2.4,
  "rsi_14": 71.3,
  "ema_50": 158.10,
  "ema_200": 149.75,
  "resistance_1": 182.00,
  "resistance_2": 195.40,
  "support_1": 164.20,
  "support_2": 151.00,
  "mood": "bullish",
  "sidekick": "moon_max",
  "chart": {"interval": "4h", "candles": 42, "file": "data/sol_ohlcv.json"}
}
```

---

## 8. LLM Prompt Şablonları

### `script_crypto.txt`
```
You write 50-second dialogue scripts for an animated stick-figure crypto commentary Short.
Characters:
- Chart Charlie: calm analyst, uses exact numbers, points at chart.
- {sidekick}: {sidekick_bio}

DATA (the ONLY numbers you may use):
{data_json}

Structure (timestamps are strict):
0-3s   sidekick hook with symbol and % change
3-10s  Charlie explains why it's trending (use volume_vs_avg, rank)
10-30s Charlie walks through chart: resistance_1, support_1, RSI context
30-42s Two scenarios: break above resistance_1 -> resistance_2; lose support_1 -> support_2
42-48s sidekick emotional reaction, Charlie dry one-liner
48-50s "Not financial advice."

Rules:
- Max 14 words per line, 8-12 lines total.
- Use ONLY numbers from DATA. Never invent prices, targets, dates or news.
- Never say buy, sell, "guaranteed", "can't lose", or price predictions as fact.
  Use conditional language: "if it breaks...", "watch...", "key level...".
- No real people, no exchange promotions, no referral codes.
Output JSON: {"lines":[{"t_start":0,"char":"...","text":"...","emotion":"...","chart_action":"none|show|draw_resistance|draw_support|highlight_scenario_up|highlight_scenario_down"}]}
```

### `validate.py` (LLM çıktısı kontrolü)
```python
import re

BANNED = ["buy now", "sell now", "guaranteed", "can't lose", "100x", "financial advice"]

def validate(script, data):
    allowed = {f"{v:.2f}" for v in data.values() if isinstance(v, (int, float))}
    allowed |= {str(round(v)) for v in data.values() if isinstance(v, (int, float))}
    for line in script["lines"]:
        text = line["text"].lower()
        if len(line["text"].split()) > 14:
            return False, f"too long: {line['text']}"
        for b in BANNED[:-1]:
            if b in text:
                return False, f"banned phrase: {b}"
        for num in re.findall(r"\d+(?:\.\d+)?", line["text"].replace(",", "")):
            if num not in allowed and not num.isdigit() or (num.isdigit() and int(num) > 10 and num not in allowed):
                return False, f"unknown number: {num}"
    if "not financial advice" not in script["lines"][-1]["text"].lower():
        return False, "missing disclaimer"
    return True, "ok"
```
Doğrulamadan geçemeyen senaryo en fazla 2 kez yeniden üretilir. Yine geçemezse o slot bir sonraki coine kayar ve Telegram'a uyarı düşer.

---

## 9. Grafik Animasyonu (Remotion)

- **Kütüphane:** Kendi SVG mum bileşenimiz (`CandleChart.tsx`). TradingView ekran görüntüsü kullanılmaz, çünkü lisans sorunu yaratır.
- **Veri:** Son 7 gün, 4 saatlik mumlar (42 mum).
- **Animasyon sırası (senaryodaki `chart_action` alanına bağlıdır):**
  1. `show`: Mumlar soldan sağa 1 saniyede çizilir.
  2. `draw_resistance`: Kırmızı kesikli çizgi soldan sağa uzar, sağ uçta `R $182.00` etiketi belirir.
  3. `draw_support`: Yeşil kesikli çizgi uzar, `S $164.20` etiketi belirir.
  4. `highlight_scenario_up`: Direncin üstüne yeşil ok çizilir, `→ $195.40` yazar.
  5. `highlight_scenario_down`: Desteğin altına kırmızı ok çizilir, `→ $151.00` yazar.
- **Charlie'nin işaretçi çubuğu**, o an anlatılan çizgiye doğru döner (açı hedef çizginin y koordinatından hesaplanır).
- **Renkler:** Yükselen mum `#22C55E`, düşen mum `#EF4444`, arka plan koyu lacivert `#0F172A`. Üst bantta coin rengi vurgu olarak kullanılır.
- **Üst bant:** Logo, sembol, fiyat, 24 saatlik % (yükselişte yeşil, düşüşte kırmızı; sayı animasyonla sayarak gelir).

**Coin logoları:** CoinGecko'nun `image` alanından indirilip `assets/logos/` klasöründe önbelleğe alınır.

---

## 10. Üretim Hattı (n8n)

```
[Cron: 09:30 / 16:30 / 22:30]
   ↓
[1] CoinGecko trending + markets → filtre (Bölüm 5) → 48 saat kuralı → coin seçimi
   ↓
[2] Binance klines (4h × 200) → Python: S/R + RSI + EMA + hacim → data.json
   ↓
[3] Ollama → script_crypto.txt → senaryo JSON
   ↓
[4] validate.py → geçmezse [3]'e dön (en fazla 2 kez)
   ↓
[5] TTS: karakter başına sabit ses → replik .wav + zaman damgaları
   ↓
[6] Rhubarb → ağız zaman çizelgesi
   ↓
[7] Remotion render: CryptoShort.tsx (grafik + karakterler + altyazı)
   ↓
[8] FFmpeg: müzik + SFX (kasa sesi, roket, ağlama) + ducking
   ↓
[9] Telegram önizleme → ✅ / ❌
   ↓
[10] Yayın: YT Shorts + TikTok + IG Reels (30 dk içinde; veri bayatlamadan)
```

**Veri tazeliği kuralı:** Render sonrası yayına kadar fiyat %3'ten fazla oynadıysa video iptal edilir ve baştan üretilir. Onay 60 dakika içinde gelmezse de video iptal edilir.

---

## 11. Başlık, Açıklama, Etiket

**Başlık şablonları (rastgele seçilir):**
- `{SYMBOL} {+/-X%} today — key levels to watch 📊`
- `Is {SYMBOL} about to break ${R1}? 👀`
- `{SYMBOL} support at ${S1} — hold or fold? 😬`

**Açıklama (sabit alt kısım):**
```
Levels calculated from 4H chart data. Educational content only — not financial advice.
Crypto is highly volatile; do your own research.
#crypto #{symbol} #shorts
```

---

## 12. Politika ve Risk

- **Yatırım tavsiyesi yok.** "Al", "sat" ya da hedef fiyat vaadi kullanılmaz. Yalnızca koşullu dil kullanılır: "eğer kırarsa…", "izlenecek seviye…". Bu hem YouTube'un yanıltıcı finans içeriği kuralları hem de SPK/SEC tarafındaki riskler için gerekli.
- **Her videoda sözlü ve yazılı feragatname** bulunur.
- **Sponsor, referans linki veya borsa tanıtımı yok.** Eklenirse, ücretli promosyon olarak YouTube'da beyan edilmesi gerekir.
- **Mikro coin yok** (Bölüm 5 filtresi).
- **Tekrarlayan içerik riski:** Grafik ve seviye formatı sabit olduğu için YouTube bunu "inauthentic content" olarak işaretleyebilir. Önlem olarak:
  - 3 hook tipi, 3 punchline tipi ve 3 karakter kombinasyonu dönüşümlü kullanılır.
  - Sahne arka planı piyasa ruh haline göre değişir (roket üssü, yağmurlu sokak, casino, uzay).
  - Haftada 1 "özel" video yapılır: haftalık özet, en iyi/en kötü coin, izleyici sorusu.
- **Telegram onayı atlanmaz.** Yanlış bir seviye veya yanlış coin logosu 2 saniyelik kontrolle yakalanır.

---

## 13. Klasör Yapısı

```
crypto-stick/
├── config.yaml              # daily_videos, filtreler, saatler, sesler
├── assets/
│   ├── characters/          # charlie.svg, max.svg, betty.svg
│   ├── backgrounds/         # rocket_base, rainy_street, casino, space
│   ├── logos/               # CoinGecko önbelleği
│   ├── sfx/                 # cash, rocket, crash, cry, boing
│   └── music/
├── data/                    # günlük data.json + ohlcv.json
├── prompts/script_crypto.txt
├── python/
│   ├── fetch.py             # CoinGecko + Binance
│   ├── levels.py            # Bölüm 6
│   └── validate.py          # Bölüm 8
├── remotion/
│   ├── CryptoShort.tsx
│   └── components/{CandleChart,LevelLine,PriceBanner,Character,Subtitle,Pointer}.tsx
├── renders/
├── history.json             # 48 saat tekrar kuralı için
└── n8n/crypto_workflow.json
```

---

## 14. Kurulum Checklist

- [ ] `fetch.py`: CoinGecko trending + markets + Binance klines, filtre uygulanmış
- [ ] `levels.py`: 10 coin üzerinde test edilmiş; seviyeler TradingView'daki grafikle gözle karşılaştırılmış
- [ ] `validate.py`: Bilinçli olarak hatalı sayı içeren 5 senaryo ile test edilmiş (hepsi reddedilmeli)
- [ ] 3 karakter SVG rig'i (8 poz, 6 ağız, işaretçi çubuklu kol)
- [ ] `CandleChart.tsx` + `LevelLine.tsx` animasyonları
- [ ] Karakter başına TTS ses ID'leri `config.yaml` içinde
- [ ] n8n workflow + Telegram onay butonu + 60 dakika zaman aşımı
- [ ] İlk 3 gün: yayın öncesi manuel seviye kontrolü
- [ ] 1. hafta sonu: izlenme oranı analizi ve hook tiplerinin ağırlıklandırılması
