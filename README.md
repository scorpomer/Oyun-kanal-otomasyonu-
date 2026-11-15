# Oyun Kanal Otomasyonu

YouTube oyun kanalı için Türkçe içerik paketi hazırlayan bir Python komut satırı aracı.
Oyun adını, platformu, stili ve süreyi verirsiniz; araç tek seferde şunları üretir:

- **İçerik planı:** başlık, açılış cümlesi, özet, bölüm akışı, çekim listesi, izleyiciye çağrı (CTA), SEO etiketleri
- **Video metni:** süreye göre bölümlere ayrılmış, zaman damgalı, seslendirmeye hazır taslak (her bölüm için hedef kelime sayısıyla)
- **YouTube bilgileri:** başlık, açıklama (bölüm zaman damgalarıyla) ve etiketler
- **Kapak (thumbnail) fikri:** kapak yazısı, tasarım önerisi ve görsel üreten yapay zekalar için hazır istem (prompt)
- **Shorts metni:** 45–60 saniyelik dikey video için saniye saniye seslendirme ve ekran yazıları

Hepsi kanalınızın **sunucu karakterine** ve tarzına göre yazılır (bkz. `kanal.json`) ve otomatik olarak `output/` klasörüne kaydedilir.

### Gemini API anahtarı olursa / olmazsa

- `.env` dosyasında `GOOGLE_API_KEY` varsa paketin tamamı **Google Gemini** ile, tek çağrıda üretilir.
- Gemini bir parçayı eksik ya da hatalı döndürürse yalnızca o parça **yerel şablondan** tamamlanır.
- Anahtar yoksa ya da Gemini çağrısı başarısız olursa (geçersiz anahtar, internet yok, kota doldu vb.)
  araç durmaz; her şeyi yerel şablonla üretir ve ekrana bir uyarı yazar.
- Hangi parçanın nereden geldiği `paket.json` içindeki `sources` alanında yazar.

> Üretilen her şey bir **taslaktır**. Yerel şablonlardaki `[KENDİ DENEYİMİNİ EKLE]` gibi yerleri kendi
> oynanışınızla doldurun ve yayınlamadan önce kontrol edin.

## Kurulum

Python **3.10 veya üstü** gerekir.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Ardından `.env` dosyasını açıp anahtarınızı yazın (isteğe bağlı):

```dotenv
GOOGLE_API_KEY=buraya_kendi_anahtarinizi_yazin
```

Anahtarı [Google AI Studio](https://aistudio.google.com/apikey) üzerinden alabilirsiniz.
`.env` dosyası `.gitignore` içindedir; anahtarınız GitHub'a yüklenmez.

İsteğe bağlı olarak farklı bir Gemini modeli seçmek için `.env` içine `GEMINI_MODEL=...` ekleyebilirsiniz
(varsayılan: `gemini-flash-latest`, yani Google'ın güncel Flash modeli).

## Kanal profili (`kanal.json`)

Kanalınızın adını, hedef kitlesini ve videoları sunan karakteri bu dosyada tanımlarsınız.
Video metni, Shorts ve YouTube açıklamaları bu karakterin ağzından yazılır.

```json
{
  "kanal_adi": "Oyun Kanalı",
  "hedef_kitle": "Türkçe konuşan, yeni oyunları merak eden oyuncular",
  "sunucu": {
    "ad": "Kaptan",
    "kisilik": "esprili, samimi ve oyunları dürüstçe değerlendiren bir oyuncu",
    "selamlama": "Merhaba arkadaşlar!",
    "kapanis": "Bir sonraki videoda görüşmek üzere, iyi oyunlar!"
  },
  "sabit_etiketler": ["oyun", "Türkçe oyun"]
}
```

Eksik bıraktığınız alanlar varsayılan değerlerle doldurulur. Dosya bozuksa araç uyarı verip varsayılan profille devam eder.
Farklı bir profil dosyası kullanmak için: `--kanal baska_kanal.json`

## Kullanım

```bash
python app.py --game "OYUN ADI" [seçenekler]
```

| Seçenek | Açıklama | Varsayılan |
|---|---|---|
| `--game` | Oyun adı (zorunlu) | — |
| `--platform` | Platform (PC, PS5, Xbox, Switch…) | `PC` |
| `--style` | Video stili | `eğlenceli ve hızlı` |
| `--tone` | Anlatım tonu | `heyecanlı` |
| `--duration` | Video süresi (dakika, en az 1) | `8` |
| `--mode` | Ekranda ne gösterilsin: `plan`, `script`, `meta`, `thumbnail`, `shorts`, `all` | `plan` |
| `--output` | Ekran çıktısı biçimi: `text` veya `json` | `text` |
| `--kanal` | Kanal profili dosyası | `kanal.json` |
| `--output-dir` | Paketin kaydedileceği klasör | `output` |
| `--no-save` | Dosyaya kaydetme, sadece ekrana yaz | — |

`--mode` yalnızca **ekranda** neyin gösterileceğini seçer; kaydedilen pakette her zaman hepsi bulunur.

### Örnekler

```bash
# İçerik planı (paket ayrıca output/ klasörüne kaydedilir)
python app.py --game "CS2" --platform "PC" --duration 8

# 15 dakikalık video için zaman damgalı metin
python app.py --game "Elden Ring" --duration 15 --mode script

# Shorts metni
python app.py --game "Minecraft" --mode shorts

# Kapak fikri
python app.py --game "Zelda" --platform "Switch" --mode thumbnail

# YouTube bilgileri JSON olarak, dosyaya kaydetmeden
python app.py --game "Stardew Valley" --mode meta --output json --no-save

# Hepsi birden
python app.py --game "Hades" --mode all
```

`python video_workflow.py ...` komutu da aynı seçeneklerle çalışır; tek farkı varsayılan `--mode` değerinin `all` olmasıdır.

### Kaydedilen dosyalar

Her çalıştırmada `output/<oyun-adı>-<tarih-saat>/` klasörü oluşur:

| Dosya | İçerik |
|---|---|
| `plan.md` | İçerik planı |
| `video_metni.txt` | Zaman damgalı video metni |
| `youtube_bilgileri.txt` | Başlık, açıklama, etiketler |
| `kapak.txt` | Kapak yazısı, tasarım ve görsel istemi |
| `shorts.txt` | Shorts metni |
| `paket.json` | Hepsi, makinenin okuyabileceği biçimde |

## Bu araç neleri yapmaz?

- Video **çekmez, kurgulamaz, seslendirmez**; metin ve fikir taslağı üretir.
- YouTube'a **otomatik yükleme yapmaz**. Bunun için YouTube Data API ve kanal sahibinin Google hesabıyla OAuth izni gerekir.
- Oyun hakkında internetten güncel bilgi toplamaz; içerikleri yayınlamadan önce kontrol edin.

## Testler

```bash
python -m pytest
```

Testler internet bağlantısı veya API anahtarı gerektirmez; Gemini çağrıları testlerde taklit edilir.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `app.py` | Komut satırı giriş noktası |
| `content_automation.py` | İçerik paketi üretimi (Gemini + yerel şablonlar), kanal profili |
| `video_workflow.py` | Çıktı biçimlendirme ve dosyaya kaydetme |
| `kanal.json` | Kanal ve sunucu karakteri ayarları |
| `tests/` | Otomatik testler |
| `nb/Orpheus_(3B)-TTS.ipynb` | Google Colab'da oluşturulmuş ayrı bir metinden sese (TTS) denemesi; uygulamanın bir parçası değildir |
