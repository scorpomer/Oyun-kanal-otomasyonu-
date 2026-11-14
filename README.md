# Kanal Otomasyon Suite

Bu depo iki otomasyonu tek yerde toplar:

- `youtube-shorts/`: trendden kısa video üretip YouTube'a yükleyen tam otomasyon
- `oyun-kanal-otomasyonu/`: oyun videosu planı, script ve YouTube metadata üretimi

## Hızlı kullanım

### 1) YouTube Shorts otomasyonu

```bash
cd youtube-shorts
pip install -r requirements.txt
python -m unittest discover -s tests
python -m shorts
```

### 2) Oyun kanal otomasyonu

```bash
cd oyun-kanal-otomasyonu
pip install -r requirements.txt
python -m pytest -q
python app.py --game "CS2" --platform "PC" --mode all
```

## CI

Bu depoda tek bir quality workflow'u vardır ve iki alt projenin testlerini ayrı job'larda çalıştırır.
