# YouTube Shorts otomasyonu

GitHub Actions üzerinde, insan müdahalesi olmadan, siz durdurana kadar çalışır. Üretim saatleri, duraklatma ve
bitiş tarihi `ayar.json`'dan ya da **Telegram botundan** yönetilir (varsayılan: Türkiye saatiyle 09:00 ve 18:00).
**Zorunlu tek dış hesap YouTube'dur**; yapay zekâ, ses ve görseller anahtarsız (ücretsiz) kaynaklardan gelir.
Davranış [ayar.json](ayar.json) dosyasından yönetilir.

## Her çalıştırmada

1. **Kanal yönetimi** (`shorts/kanal.py`):
   - Abone, toplam izlenme ve video sayısı günlük olarak kaydedilir; YouTube Analytics açıksa son 28 günün
     günlük izlenme/abone kazancı ve her videonun izlenme oranı, kazandırdığı abone sayısı alınır.
   - Kanal açıklaması, anahtar kelimeler, dil/ülke ve kapak görseli **boşsa** doldurulur (dolu olan ezilmez;
     eski değer kayda yedeklenir). Kapak görseli kanal adıyla otomatik çizilir.
   - Son yorumlar okunur: soru ve övgülere yerel yapay zekâyla kısa yanıt verilir (çalıştırma başına en çok 8),
     bağlantılı/reklam yorumları "incelemede" bekletilir (YouTube Studio'dan geri alınabilir).
2. **Trend:** Google Trends'ten Türkiye'de o gün en çok aranan konular; son 7 günde işlenen (ya da benzer) konu
   tekrar seçilmez.
3. **Konu seçimi:** Konunun türü (spor, dizi/ünlü, teknoloji, ekonomi, eğitim, hava, diğer) bulunur; sıralama
   türün kanalda ne kadar izlendiğine (ve Analytics varsa ne kadar abone kazandırdığına) göre yapılır.
4. **Hassas konu filtresi:** Siyaset, yargı, ölüm, kaza, deprem, terör, bahis, din gibi konular sabit kelime
   listesiyle elenir.
5. **Kaynak ve metin:** Haber sitelerinden haberin ilk paragrafları okunur; yapay zekâ yalnızca bu kaynaktan
   10 cümlelik metin yazar. Varsayılan model GitHub sunucusunda çalışan **Ollama `qwen3:4b`** (anahtarsız);
   o olmazsa anahtar varsa Gemini/Claude. Metindeki özel isim ve sayılar kaynakta aranır; uydurma varsa düzelttirilir.
6. **Seslendirme:** edge-tts (`tr-TR-AhmetNeural`, anahtarsız). Ulaşılamazsa sunucuda çalışan çevrimdışı
   **Piper** Türkçe sesine geçilir. Ses, ücretsiz bir "stüdyo zinciri"nden geçer (uğultu kesme, sert "s"
   yumuşatma, sıkıştırma, netlik, YouTube ses seviyesi).
7. **Görüntü:** Konudaki kişi/takım/dizi/yerin gerçek fotoğrafları **Wikimedia Commons**'tan (anahtarsız, özgür
   lisanslı) alınır; yatay fotoğraflar bulanık zemin üstüne ortalanır. `PEXELS_API_KEY` varsa stok videolar
   da eklenir. Sahneler ~3,5 saniyede bir yumuşak geçişle değişir. Poppins yazı tipiyle karaoke altyazı
   (okunan kelime sarı), açılış kartı, ilerleme çubuğu ve söylenen sayılar için ayrıca vurgu etiketi
   ("12 MİLYON EURO").
8. **YouTube:** Video **herkese açık** yüklenir; kategori türe göre seçilir. Açıklamaya kanca cümlesi, haber
   kaynakları, görsel atıfları (CC lisansı gereği) ve yapay zekâ bildirimi eklenir. Türkçe altyazı dosyası da
   yüklenir.
9. **Rapor ve plan:** [RAPOR.md](RAPOR.md) her çalıştırmada yenilenir: kanal durumu, günlük gidişat tablosu,
   sonraki abone hedefine tahmini süre, öncelikli tür, izlenme oranı yorumu, son yorumlar ve
   **senin yapman gerekenler** listesi.

Her çalıştırmanın videosu 7 gün boyunca Actions sayfasında indirilebilir (`shorts-N`).
Elle çalıştırma: Actions > Shorts otomasyonu > Run workflow ("Sadece video üret" seçilirse YouTube'a yüklenmez).

## Zamanlama ve Telegram

- `kontrol.yml` saatte bir (birkaç saniyelik bir iş) çalışır: Telegram komutlarını işler, `ayar.json > zamanlama`
  saatlerinde `shorts.yml` üretimini başlatır, hata veren üretimi 50 dakika sonra bir kez yeniden dener,
  bitiş tarihi gelince üretimi durdurur. Durumu `kontrol.json`'da tutar.
- GitHub zamanlayıcısı gecikebildiği için bir saat 3 saat içinde yakalanır; komutlara yanıt en geç ~1 saat sürer.
- Ana daldaki kalite/test iş akışı başarısız olursa, yalnızca başarısız adımlar bir kez otomatik yeniden çalıştırılır
  (geçici GitHub runner/ağ sorunları için); eski hatalar tekrar tetiklenmez.
- Depo özel olduğu için GitHub'ın ücretsiz aylık 2000 dakikası geçerlidir: kontrol ~720, iki günlük üretim
  ~900-1000 dakika tutar. Depo herkese açık yapılırsa sınır kalkar.

### Telegram kurulumu

1. Telegram'da **@BotFather**'a `/newbot` yaz, bota ad ver; verdiği belirteci GitHub > Settings > Secrets and
   variables > Actions'ta `TELEGRAM_BOT_TOKEN` adıyla kaydet.
2. Kendi botuna `/start` yaz. Bir sonraki kontrolde (hemen istersen Actions > Kontrol > Run workflow) bot,
   **ilk `/start` yazan sohbeti sahip olarak kendiliğinden kaydeder** (`ayar.json > telegram > sohbet_id`);
   başka bir şey eklemen gerekmez. İstersen `TELEGRAM_CHAT_ID` gizli ayarıyla elle de belirleyebilirsin.
3. Bot sana kurulum durumunu (ne tamam, ne eksik, eksik nasıl tamamlanır) ve komut listesini yollar.
   Sonradan `/kurulum` ile yeniden denetleyebilirsin.

| Komut | İş |
|---|---|
| `/durum` | Abone, izlenme, son video, zamanlama |
| `/son` | Son 5 video ve izlenmeleri |
| `/rapor` | Gidişat, hedef tahmini, yapılacaklar |
| `/kurulum` | Eksik anahtar ve izinlerin denetimi |
| `/uret` | Hemen video üret ve yayınla |
| `/deneme` | Yayınlamadan deneme videosu |
| `/duraklat`, `/devam` | Otomatik üretimi durdur / sürdür |
| `/saatler 09:00 18:00` | Üretim saatleri (Türkiye saati, en çok 6) |
| `/bitis 2027-01-31`, `/bitis yok` | Bitiş tarihi / süresiz |
| `/gizlilik public` ya da `private` | Yayın durumu |
| `/yorum ac` ya da `kapat` | Yorum yanıtlama |
| `/ses ahmet` ya da `emel` | Seslendirme sesi |

## ayar.json

| Alan | Anlamı |
|---|---|
| `gizlilik` | `public` otomatik yayın, `private` önce Studio'dan kontrol |
| `yapay_zeka` | `yerel` (önce anahtarsız Ollama) ya da `bulut` (önce Gemini/Claude) |
| `ses` | edge-tts ses adı, hız ve perde (ör. `tr-TR-EmelNeural` kadın sesi) |
| `kanal` | Boşsa yazılacak kanal açıklaması, anahtar kelimeler, kapak sloganı; `marka_uygula: false` kapatır |
| `yorumlar` | `yanitla`, `en_cok_yanit`, `spam_beklet` |
| `altyazi_yukle` | YouTube'a altyazı dosyası yüklensin mi |
| `zamanlama` | `aktif`, `saatler` (TR), `bitis` (YYYY-AA-GG ya da null), `gunluk_en_cok` |
| `telegram` | `sohbet_id` (TELEGRAM_CHAT_ID gizli ayarı yoksa) |

## Gizli ayarlar (Settings > Secrets and variables > Actions)

| Ad | Durum / nereden |
|---|---|
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | **Zorunlu.** `python yetki_al.py client_secret.json` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` | İsteğe bağlı yedek yapay zekâ |
| `PEXELS_API_KEY` | İsteğe bağlı stok video (pexels.com/api) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | İsteğe bağlı: Telegram'dan yönetim ve bildirim (yukarıya bakın) |

### YouTube izinleri

`yetki_al.py` şu izinleri ister: video yükleme, istatistik okuma, `youtube.force-ssl` (yorum yanıtlama, yorum
bekletme, kanal açıklaması/kapak, altyazı) ve `yt-analytics.readonly`. Eski anahtar (yalnızca yükleme + okuma)
çalışmaya devam eder; eksik izin gerektiren adımlar atlanır ve RAPOR.md'de "Senin yapman gerekenler"e yazılır.
YouTube Analytics için Google Cloud Console'da projede **YouTube Analytics API** etkinleştirilmelidir.

## Yedekler

- **Haftalık arşiv** (`yedek.yml`, her Pazar): yapilanlar.json, ayar.json, kontrol.json, RAPOR.md, marka/ ve
  bir manifest (her dosyanın sha256 özeti) tek bir `.tar.gz` olarak **Releases** sayfasına konur. Son 12 hafta tutulur.
- **Her video** (`shorts.yml`): shorts.mp4 ve bilgi.json, `video-<çalıştırma no>` adlı kendi Release'inde kalır;
  Actions'taki 7 günlük artifact'ten bağımsızdır.
- **Git geçmişi:** Her değişiklik zaten commit olarak tutulur.
- **Sırlar yedeklenmez.** Yedek oluşturulurken metinlerde token benzeri bir değer görülürse arşiv yazılmaz ve hata
  verilir (`shorts/yedek.py`).
- Geri yükleme: arşivi açıp `manifest.json` içindeki dosyaları depoya kopyalamak yeterli.

## API'nin yapamadıkları

- **Profil fotoğrafı** API ile değiştirilemez: [marka/profil.png](marka/profil.png) bir kez elle yüklenir
  (YouTube Studio > Özelleştirme > Marka).
- **Kanal adı** API ile değiştirilemez (Studio > Özelleştirme > Temel bilgiler).
- **Topluluk ayarları** (engellenen kelimeler, yorum denetim düzeyi), yorum sabitleme ve kalp bırakma API'de yok;
  sistem yalnızca tek tek yorumlara yanıt verir ve spam'i bekletir.

## Yerel çalıştırma

```
pip install -r requirements.txt   # ffmpeg de kurulu olmalı
KURU_CALISMA=1 OLLAMA_URL=http://localhost:11434 python -m shorts   # video cikti/ klasörüne yazılır
```

## Testler

`python -m unittest discover -s tests`

Yazı tipi: Poppins (SIL Open Font License, `shorts/yazitipi/OFL.txt`).
