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

## Örnek kullanım

```bash
python app.py --game "Helldivers 2" --platform "PC" --style "eğlenceli ve hızlı" --tone "heyecanlı" --output text
python app.py --game "Zelda" --platform "Switch" --output json
```
