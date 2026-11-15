from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"


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


def generate_content_plan(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
    api_key: str | None = None,
) -> Dict[str, Any]:
    if not game_name or not game_name.strip():
        raise ValueError("Oyun adı boş bırakılamaz.")
    if duration_minutes < 1:
        raise ValueError("Video süresi en az 1 dakika olmalı.")

    plan = build_local_plan(game_name, platform, style, tone, duration_minutes)

    if not api_key:
        return plan

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = f"""
        Aşağıdaki bilgileri kullanarak YouTube oyun videosu için kısa ama profesyonel bir içerik planı üret.
        Output sadece JSON olmalı. Format:
        {{
          "title": "...",
          "hook": "...",
          "summary": "...",
          "outline": ["...","..."],
          "shot_list": ["...","..."],
          "cta": "...",
          "seo_tags": ["...","..."]
        }}

        Oyun: {game_name}
        Platform: {platform}
        Stil: {style}
        Ton: {tone}
        Video süresi: {duration_minutes} dakika
        """

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
            contents=prompt,
        )
        raw_text = getattr(response, "text", None) or str(response)
        payload = _extract_json_payload(raw_text)

        # Modelin eksik ya da hatalı döndürdüğü alanları yerel plandan tamamla.
        for key in ("title", "hook", "summary", "cta"):
            if not isinstance(payload.get(key), str) or not payload[key].strip():
                payload[key] = plan[key]
        for key in ("outline", "shot_list", "seo_tags"):
            value = payload.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                payload[key] = plan[key]

        payload.setdefault("platform", platform)
        payload.setdefault("style", style)
        payload.setdefault("tone", tone)
        payload.setdefault("duration_minutes", duration_minutes)
        return payload
    except Exception as exc:
        print(
            f"Uyarı: Gemini ile plan üretilemedi, yerel yedek plan kullanılıyor ({exc}).",
            file=sys.stderr,
        )
        return plan


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


__all__ = ["build_local_plan", "generate_content_plan", "render_markdown"]
