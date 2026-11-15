# Oyun Kanal Otomasyonu

YouTube oyun kanalı için Türkçe içerik hazırlayan küçük bir Python komut satırı aracı.
Oyun adını, platformu, stili ve süreyi verirsiniz; araç size şunları üretir:

- **İçerik planı:** video başlığı, açılış cümlesi, özet, bölüm akışı, çekim listesi, izleyiciye çağrı (CTA) ve SEO etiketleri
- **Video metni (script):** seslendirmeye hazır, bölüm bölüm anlatım taslağı
- **YouTube bilgileri:** başlık, açıklama ve etiketler

### Gemini API anahtarı olursa / olmazsa

- `.env` dosyasında `GOOGLE_API_KEY` varsa **içerik planı** Google Gemini ile üretilir.
- Anahtar yoksa ya da Gemini çağrısı başarısız olursa (geçersiz anahtar, internet yok, kota doldu vb.)
  araç durmaz; **yerel şablonla** plan üretir ve ekrana bir uyarı yazar.
- **Video metni ve YouTube bilgileri** her zaman yerel şablonla üretilir (Gemini kullanılmaz).

> Üretilen her şey bir **taslaktır**. Yayınlamadan önce kendi oynanış deneyiminizle kontrol edip düzenleyin.

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

Anahtarı [Google AI Studio](https://aistudio.google.com/apikey) üzerinden ücretsiz alabilirsiniz.
`.env` dosyası `.gitignore` içindedir; anahtarınız GitHub'a yüklenmez.

İsteğe bağlı olarak farklı bir Gemini modeli seçmek için `.env` içine `GEMINI_MODEL=...` ekleyebilirsiniz
(varsayılan: `gemini-flash-latest`, yani Google'ın güncel Flash modeli).

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
| `--mode` | Ne üretilsin: `plan`, `script`, `meta`, `all` | `plan` |
| `--output` | Çıktı biçimi: `text` veya `json` | `text` |

### Örnekler

```bash
# Sadece içerik planı (varsayılan)
python app.py --game "CS2" --platform "PC" --duration 8

# Plan, ton ve stil belirterek
python app.py --game "Helldivers 2" --style "eğlenceli ve hızlı" --tone "heyecanlı" --mode plan

# Sadece video metni
python app.py --game "Zelda" --platform "Switch" --mode script

# Sadece YouTube başlık/açıklama/etiketleri, JSON olarak
python app.py --game "Elden Ring" --mode meta --output json

# Hepsi birden
python app.py --game "Stardew Valley" --mode all

# Çıktıyı dosyaya kaydetmek için
python app.py --game "Minecraft" --mode all > minecraft.md
```

`--output json` seçildiğinde yalnızca `--mode` ile istenen bölüm JSON olarak yazdırılır
(`all` seçilirse hepsi).

`python video_workflow.py ...` komutu da aynı seçeneklerle çalışır; tek farkı varsayılan `--mode` değerinin `all` olmasıdır.

## Testler

```bash
python -m pytest
```

Testler internet bağlantısı veya API anahtarı gerektirmez; Gemini çağrıları testlerde taklit edilir.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `app.py` | Komut satırı giriş noktası |
| `content_automation.py` | İçerik planı üretimi (Gemini + yerel yedek) |
| `video_workflow.py` | Video metni, YouTube bilgileri ve çıktı biçimlendirme |
| `tests/` | Otomatik testler |
| `nb/Orpheus_(3B)-TTS.ipynb` | Google Colab'da oluşturulmuş ayrı bir metinden sese (TTS) denemesi; uygulamanın bir parçası değildir |
