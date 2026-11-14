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
- Artık video scripti ve YouTube meta bilgileri üretebilir

## Yeni kullanım örnekleri

```bash
python app.py --game "Helldivers 2" --platform "PC" --style "eğlenceli ve hızlı" --tone "heyecanlı" --mode plan
python app.py --game "Zelda" --platform "Switch" --mode script
python app.py --game "Elden Ring" --platform "PC" --mode meta --output json
python app.py --game "Stardew Valley" --platform "PC" --mode all
```

## Geliştirme aşaması

Projede şu alanlar genişletilebilir:

- oyun verilerinin otomatik çekilmesi
- konu başlığı ve thumbnail önerileri
- video seslendirme scripti üretimi
- otomatik YouTube açıklaması + hashtag üretimi
- web arayüzü (Streamlit / Flask)
