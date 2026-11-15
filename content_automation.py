"""Oyun videosu içerik paketi üretimi: Gemini (varsa) + yerel yedek şablonlar."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_CHANNEL_FILE = Path(__file__).resolve().parent / "kanal.json"
WORDS_PER_MINUTE = 140  # Türkçe seslendirmede ortalama konuşma hızı

DEFAULT_CHANNEL: Dict[str, Any] = {
    "kanal_adi": "Oyun Kanalı",
    "hedef_kitle": "Türkçe konuşan, yeni oyunları merak eden oyuncular",
    "sunucu": {
        "ad": "Kaptan",
        "kisilik": "esprili, samimi ve oyunları dürüstçe değerlendiren bir oyuncu",
        "selamlama": "Merhaba arkadaşlar!",
        "kapanis": "Bir sonraki videoda görüşmek üzere, iyi oyunlar!",
    },
    "sabit_etiketler": ["oyun", "Türkçe oyun"],
}


# ---------------------------------------------------------------------------
# Kanal profili
# ---------------------------------------------------------------------------

def load_channel_profile(path: str | Path | None = None) -> Dict[str, Any]:
    """kanal.json dosyasını okur; dosya yoksa ya da hatalıysa varsayılan profili kullanır."""
    profile = copy.deepcopy(DEFAULT_CHANNEL)
    target = Path(path) if path else DEFAULT_CHANNEL_FILE
    if not target.exists():
        if path:
            print(f"Uyarı: kanal dosyası bulunamadı ({target}); varsayılan kanal profili kullanılıyor.", file=sys.stderr)
        return profile
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("kanal dosyası bir JSON nesnesi olmalı")
    except (OSError, ValueError) as exc:
        print(f"Uyarı: kanal dosyası okunamadı ({exc}); varsayılan kanal profili kullanılıyor.", file=sys.stderr)
        return profile

    for key in ("kanal_adi", "hedef_kitle"):
        if isinstance(data.get(key), str) and data[key].strip():
            profile[key] = data[key].strip()
    presenter = data.get("sunucu")
    if isinstance(presenter, dict):
        for key in ("ad", "kisilik", "selamlama", "kapanis"):
            if isinstance(presenter.get(key), str) and presenter[key].strip():
                profile["sunucu"][key] = presenter[key].strip()
    tags = data.get("sabit_etiketler")
    if isinstance(tags, list):
        profile["sabit_etiketler"] = [str(tag).strip() for tag in tags if str(tag).strip()]
    return profile


# ---------------------------------------------------------------------------
# Yerel (çevrimdışı) şablonlar
# ---------------------------------------------------------------------------

def _format_time(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def build_local_plan(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
) -> Dict[str, Any]:
    title = f"{game_name} {platform} ile {duration_minutes} dakikalık {style} incelemesi"
    hook = (
        f"Bugün {game_name} oyununu {platform} üzerinde inceleyeceğiz; "
        "görünüşe göre herkesin konuştuğu bu oyun gerçekten beklediği kadar iyi mi?"
    )

    outline = [
        "Oyun fikri ve görsel estetiği",
        "İlk izlenim ve kontrol deneyimi",
        "Oyuncu ilerleyişi ve içerik derinliği",
        "Görsel ve ses kalitesi",
        "Sonuç: İzlenmeye değer mi?",
    ]

    shot_list = [
        "Açılış sahnesi ve kısa açıklama",
        "Oyun menüsü ve genel görünüm",
        "Ana oynanışın ilk dakikaları",
        "Öne çıkan mekanikler ve zorluklar",
        "Son karar ve öneri",
    ]

    return {
        "title": title,
        "hook": hook,
        "platform": platform,
        "style": style,
        "tone": tone,
        "duration_minutes": duration_minutes,
        "summary": (
            f"{game_name} için {style} bir içerik üretimi planı. "
            "İzleyicinin dikkatini çekmek için güçlü bir açılış, kısa hikâye akışı, "
            "oyunun güçlü yönlerini vurgulayan sahneler ve net bir sonuç sunulur."
        ),
        "outline": outline,
        "shot_list": shot_list,
        "cta": "Bu videoyu beğendiyseniz yorumlarda hangi oyunu bir sonraki videoda görmek istediğinizi yazın!",
        "seo_tags": [game_name, platform, style, "oyun incelemesi", "youtube oyun videosu"],
    }


_BODY_TOPICS = [
    ("İlk izlenim", "İlk olarak oyunun genel hissini konuşalım. Görsel tasarım, menü akışı ve ilk dakikalardaki izlenim çok önemli. [KENDİ İLK İZLENİMİNİ EKLE]"),
    ("Kontroller ve oynanış", "Sonra kontrol sistemini ve oynanış akışını inceleyelim. Bu oyun gerçekten oyuncuyu sürece bağlayabiliyor mu?"),
    ("Öne çıkan mekanikler", "Şimdi {game} oyununu farklı kılan mekaniklere bakalım. Bu bölümde kendi oynanış kaydınızdan örnekler gösterin."),
    ("Görsel ve ses", "Görsel ve ses tasarımı deneyime ne katıyor? {platform} üzerindeki performansı ve akıcılığı da değerlendirelim."),
    ("İçerik ve ilerleme", "Oyunun içerik derinliğine ve ilerleme sistemine geçelim. Oyuncuyu uzun süre oyunda tutacak kadar çeşitlilik var mı?"),
    ("Zorluk ve denge", "Zorluk seviyesi yeni başlayanlar ve deneyimli oyuncular için dengeli mi? Sizi en çok zorlayan anı anlatın."),
    ("Güçlü ve zayıf yönler", "Oyunun güçlü ve zayıf yönlerini toparlayalım. İster eğlence odaklı bir izleyici olun, ister detaycı bir oyuncu; herkes için net bir fikir oluşturalım."),
    ("Kimlere uygun?", "Bu oyun hangi tür oyuncular için daha uygun? Benzer oyunları sevenlere ne vaat ediyor?"),
]


def build_local_script(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
    channel: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Süreye göre bölüm sayısı ve zaman damgaları ayarlanmış video metni üretir."""
    channel = channel or DEFAULT_CHANNEL
    presenter = channel["sunucu"]
    total = duration_minutes * 60
    intro_len = min(30.0, total * 0.15)
    outro_len = min(60.0, total * 0.2)
    body_count = max(1, min(len(_BODY_TOPICS), round(duration_minutes / 1.5)))
    body_len = (total - intro_len - outro_len) / body_count

    sections = [
        {
            "title": "Açılış",
            "start": "0:00",
            "text": (
                f"{presenter['selamlama']} Ben {presenter['ad']}, burası {channel['kanal_adi']}! "
                f"Bugün {game_name} oyununu {platform} üzerinde {style} bir tempoda, {tone} bir anlatımla ele alıyoruz."
            ),
            "target_words": int(intro_len / 60 * WORDS_PER_MINUTE),
        }
    ]
    for index in range(body_count):
        title, text = _BODY_TOPICS[index]
        sections.append(
            {
                "title": title,
                "start": _format_time(intro_len + index * body_len),
                "text": text.format(game=game_name, platform=platform),
                "target_words": int(body_len / 60 * WORDS_PER_MINUTE),
            }
        )
    sections.append(
        {
            "title": "Sonuç",
            "start": _format_time(total - outro_len),
            "text": (
                f"Kısacası, {game_name} oyununu {platform} üzerinde oynarken ne hissettiniz? Siz bu oyunu alır mıydınız? "
                f"Yorumlarda düşüncelerinizi yazın. {presenter['kapanis']}"
            ),
            "target_words": int(outro_len / 60 * WORDS_PER_MINUTE),
        }
    )
    return sections


def build_local_metadata(
    game_name: str,
    platform: str,
    style: str,
    duration_minutes: int,
    channel: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    channel = channel or DEFAULT_CHANNEL
    title = f"{game_name} {platform} İncelemesi | {duration_minutes} Dakika {style} Oynanış"
    description = (
        f"{game_name} oyununun {platform} sürümünü deneyimledik. "
        "Oynanış, grafikler, hikâye, zorluk seviyeleri ve genel öneri hakkındaki düşüncelerimizi paylaşıyoruz. "
        f"Bu video {style} bir anlatımla hazırlanmıştır.\n\n"
        f"Abone olmayı ve bildirimleri açmayı unutmayın! — {channel['kanal_adi']}"
    )
    tags = [
        game_name,
        platform,
        "oyun incelemesi",
        style,
        "youtube oyun videosu",
        "oyun analizi",
        f"{platform} oyun",
        *channel.get("sabit_etiketler", []),
    ]
    return {"title": title, "description": description, "tags": list(dict.fromkeys(tags))}


def build_local_thumbnail(game_name: str, platform: str, style: str, tone: str) -> Dict[str, Any]:
    return {
        "text": f"{game_name.upper()} DEĞER Mİ?",
        "visual": (
            f"Solda {game_name} oyunundan en dikkat çekici sahne, sağda şaşkın/heyecanlı yüz ifadesiyle sunucu. "
            "Büyük, kalın, sarı-beyaz yazı; yüksek kontrast; arka plan hafif bulanık."
        ),
        "prompt": (
            f"YouTube kapak görseli, 16:9, {game_name} oyununun atmosferini yansıtan dramatik bir sahne, "
            f"{style} ve {tone} bir hava, canlı renkler, yüksek kontrast, sinematik ışık, "
            "sağ tarafta yazı için boş alan, metin içermesin"
        ),
    }


def build_local_shorts(game_name: str, platform: str, channel: Dict[str, Any] | None = None) -> Dict[str, Any]:
    channel = channel or DEFAULT_CHANNEL
    return {
        "title": f"{game_name} hakkında bunu biliyor muydun? #shorts",
        "description": f"{game_name} ({platform}) hakkında 45 saniyelik kısa bakış. Uzun inceleme kanalda! #shorts #oyun",
        "beats": [
            {"time": "0-3 sn", "voice": f"{game_name} gerçekten bu kadar iyi mi? Hemen bakalım!", "on_screen": "BU KADAR İYİ Mİ?"},
            {"time": "3-15 sn", "voice": "İlk dikkat çeken şey: [OYUNUN EN İLGİNÇ ÖZELLİĞİNİ EKLE].", "on_screen": "1. ÖZELLİK"},
            {"time": "15-30 sn", "voice": "Ama asıl şaşırtan şu: [KENDİ DENEYİMİNDEN BİR AN EKLE].", "on_screen": "ASIL ŞAŞIRTAN"},
            {"time": "30-45 sn", "voice": "Sen olsan oynar mıydın? Yorumlara yaz, tam inceleme kanalımızda!", "on_screen": "YORUMLARA YAZ 👇"},
        ],
    }


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _extract_json_payload(text: str) -> Dict[str, Any]:
    """Model yanıtından JSON nesnesini çıkarır; ```json bloklarını ve çevre metni tolere eder."""
    if not text or not text.strip():
        raise ValueError("Boş model yanıtı.")

    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(cleaned[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("Model JSON nesnesi döndürmedi.")
    return payload


def _build_prompt(game_name: str, platform: str, style: str, tone: str, duration_minutes: int, channel: Dict[str, Any]) -> str:
    presenter = channel["sunucu"]
    schema = {
        "plan": {
            "title": "...", "hook": "...", "summary": "...",
            "outline": ["..."], "shot_list": ["..."], "cta": "...", "seo_tags": ["..."],
        },
        "script": [{"title": "bölüm adı", "start": "0:00", "text": "seslendirilecek metin"}],
        "youtube": {"title": "...", "description": "...", "tags": ["..."]},
        "thumbnail": {"text": "kapakta yazacak kısa metin", "visual": "kapak tasarımı", "prompt": "görsel üretim yapay zekası için ayrıntılı istem"},
        "shorts": {
            "title": "... #shorts", "description": "...",
            "beats": [{"time": "0-3 sn", "voice": "...", "on_screen": "..."}],
        },
    }
    return f"""Sen "{channel['kanal_adi']}" adlı Türkçe YouTube oyun kanalının içerik editörüsün.
Hedef kitle: {channel['hedef_kitle']}.
Videoları sunan karakter: {presenter['ad']} — {presenter['kisilik']}.
Sunucunun açılış cümlesi: "{presenter['selamlama']}", kapanış cümlesi: "{presenter['kapanis']}".

Aşağıdaki oyun için eksiksiz bir içerik paketi hazırla. Kurallar:
- Her şey Türkçe olsun, sunucunun kişiliğiyle ve kendi ağzından yazılsın.
- Video metni ("script") yaklaşık {duration_minutes * WORDS_PER_MINUTE} kelime olsun, {duration_minutes} dakikaya yayılsın; her bölümün başlangıç zamanını "dakika:saniye" olarak ver.
- İlk 10 saniyede izleyiciyi yakalayan güçlü bir kanca kullan.
- Oyun hakkında emin olmadığın bilgileri uydurma; içerik üreticisinin kendi deneyimini eklemesi gereken yerlere [KENDİ DENEYİMİNİ EKLE] yaz.
- YouTube başlığı 70 karakteri geçmesin; açıklamada bölüm zaman damgalarını da listele.
- Shorts 60 saniyeyi geçmesin, dikey video için yazılsın, ilk 3 saniyede merak uyandırsın.
- Yalnızca aşağıdaki şemaya uyan geçerli JSON döndür.

Şema: {json.dumps(schema, ensure_ascii=False)}

Oyun: {game_name}
Platform: {platform}
Stil: {style}
Ton: {tone}
Video süresi: {duration_minutes} dakika
"""


def _call_gemini(prompt: str, api_key: str) -> Dict[str, Any]:
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )
    raw_text = getattr(response, "text", None) or str(response)
    return _extract_json_payload(raw_text)


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_text(item) for item in value)


def _merge_fields(generated: Any, fallback: Dict[str, Any], text_keys: tuple, list_keys: tuple = ()) -> Dict[str, Any] | None:
    """Model çıktısındaki geçerli alanları alır, eksikleri yedekten tamamlar. Hiç geçerli alan yoksa None döner."""
    if not isinstance(generated, dict):
        return None
    merged = dict(fallback)
    used = False
    for key in text_keys:
        if _is_text(generated.get(key)):
            merged[key] = generated[key].strip()
            used = True
    for key in list_keys:
        if _is_text_list(generated.get(key)):
            merged[key] = [item.strip() for item in generated[key]]
            used = True
    return merged if used else None


def _valid_script(value: Any) -> List[Dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    sections = []
    for item in value:
        if isinstance(item, dict) and _is_text(item.get("text")):
            sections.append(
                {
                    "title": item["title"].strip() if _is_text(item.get("title")) else f"Bölüm {len(sections) + 1}",
                    "start": item["start"].strip() if _is_text(item.get("start")) else "",
                    "text": item["text"].strip(),
                }
            )
    return sections or None


def _valid_beats(value: Any) -> List[Dict[str, str]] | None:
    if not isinstance(value, list):
        return None
    beats = [
        {
            "time": item["time"].strip() if _is_text(item.get("time")) else "",
            "voice": item["voice"].strip(),
            "on_screen": item["on_screen"].strip() if _is_text(item.get("on_screen")) else "",
        }
        for item in value
        if isinstance(item, dict) and _is_text(item.get("voice"))
    ]
    return beats or None


# ---------------------------------------------------------------------------
# Ana üretim fonksiyonları
# ---------------------------------------------------------------------------

def generate_content_package(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
    api_key: str | None = None,
    channel: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Plan, video metni, YouTube bilgileri, kapak fikri ve Shorts metninden oluşan paketi üretir.

    API anahtarı varsa tek bir Gemini çağrısı yapılır; modelin döndürmediği ya da hatalı
    döndürdüğü her parça yerel şablondan tamamlanır. Hangi parçanın nereden geldiği
    ``sources`` alanında yazar.
    """
    if not game_name or not game_name.strip():
        raise ValueError("Oyun adı boş bırakılamaz.")
    if duration_minutes < 1:
        raise ValueError("Video süresi en az 1 dakika olmalı.")

    channel = channel or load_channel_profile()
    package: Dict[str, Any] = {
        "plan": build_local_plan(game_name, platform, style, tone, duration_minutes),
        "script": build_local_script(game_name, platform, style, tone, duration_minutes, channel),
        "youtube": build_local_metadata(game_name, platform, style, duration_minutes, channel),
        "thumbnail": build_local_thumbnail(game_name, platform, style, tone),
        "shorts": build_local_shorts(game_name, platform, channel),
    }
    sources = {part: "yerel şablon" for part in package}
    package["channel"] = channel

    if api_key:
        try:
            generated = _call_gemini(
                _build_prompt(game_name, platform, style, tone, duration_minutes, channel), api_key
            )
            parts = {
                "plan": _merge_fields(
                    generated.get("plan"), package["plan"],
                    ("title", "hook", "summary", "cta"), ("outline", "shot_list", "seo_tags"),
                ),
                "script": _valid_script(generated.get("script")),
                "youtube": _merge_fields(generated.get("youtube"), package["youtube"], ("title", "description"), ("tags",)),
                "thumbnail": _merge_fields(generated.get("thumbnail"), package["thumbnail"], ("text", "visual", "prompt")),
                "shorts": None,
            }
            shorts = _merge_fields(generated.get("shorts"), package["shorts"], ("title", "description"))
            beats = _valid_beats((generated.get("shorts") or {}).get("beats") if isinstance(generated.get("shorts"), dict) else None)
            if beats:
                shorts = dict(shorts or package["shorts"], beats=beats)
            parts["shorts"] = shorts

            for name, value in parts.items():
                if value:
                    package[name] = value
                    sources[name] = "Gemini"
            if all(source == "yerel şablon" for source in sources.values()):
                raise ValueError("Model yanıtında kullanılabilir içerik yok.")
        except Exception as exc:
            print(
                f"Uyarı: Gemini ile içerik üretilemedi, yerel şablonlar kullanılıyor ({exc}).",
                file=sys.stderr,
            )

    package["plan"].update(platform=platform, style=style, tone=tone, duration_minutes=duration_minutes)
    package["sources"] = sources
    return package


def generate_content_plan(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
    api_key: str | None = None,
) -> Dict[str, Any]:
    """Geriye uyumluluk için: yalnızca içerik planını döndürür."""
    return generate_content_package(game_name, platform, style, tone, duration_minutes, api_key)["plan"]


def render_markdown(plan: Dict[str, Any]) -> str:
    outline = "\n".join(f"{index}. {item}" for index, item in enumerate(plan.get("outline", []), start=1))
    shot_list = "\n".join(f"- {item}" for item in plan.get("shot_list", []))
    seo_tags = ", ".join(plan.get("seo_tags", []))

    return f"""# {plan.get('title', 'Oyun İçerik Planı')}

## Açılış cümlesi
{plan.get('hook', 'Oyun hakkında güçlü bir giriş hazırlıyoruz.')}

## Özet
{plan.get('summary', 'Bu video için net bir hikâye akışı oluşturuluyor.')}

## Video akışı
{outline}

## Görüntü planı
{shot_list}

## CTA
{plan.get('cta', 'Abone olun ve sonraki videoda devam edelim.')}

## SEO etiketleri
{seo_tags}
"""


__all__ = [
    "build_local_plan",
    "build_local_script",
    "build_local_metadata",
    "build_local_thumbnail",
    "build_local_shorts",
    "generate_content_package",
    "generate_content_plan",
    "load_channel_profile",
    "render_markdown",
]
