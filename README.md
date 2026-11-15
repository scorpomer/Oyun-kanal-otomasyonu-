# Oyun-kanal-otomasyonu-
YouTube oyun kanalı için yapay zeka içerik otomasyonu.

## Hızlı Başlangıç

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env dosyasına Google API anahtarınızı ekleyin
python app.py --game "CS2" --platform "PC" --duration 8
```

## Özellikler

- Oyun başlığı ve platform bazlı içerik planı üretir
- Video açılış cümlesi, özet, akış ve CTA hazırlar
- Google Gemini API key mevcutsa canlı içerik planı denemesi yapar
- API key yoksa yerel akıllı fallback çalışır
- Video scripti ve YouTube meta bilgileri üretir

## Kullanım örnekleri

```bash
python app.py --game "Helldivers 2" --platform "PC" --style "eğlenceli ve hızlı" --tone "heyecanlı" --mode plan
python app.py --game "Zelda" --platform "Switch" --mode script
python app.py --game "Elden Ring" --platform "PC" --mode meta --output json
python app.py --game "Stardew Valley" --platform "PC" --mode all
```

`--output json` kullanırken çıktı seçilen `--mode` ile birebir eşleşir (`plan`, `script`, `meta` veya `all`).

## Test

```bash
python -m pytest -q
```
