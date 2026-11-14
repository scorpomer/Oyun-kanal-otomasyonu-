from __future__ import annotations

from typing import Any, Dict, List

from content_automation import generate_content_plan


def build_script_lines(game_name: str, platform: str, tone: str, style: str, duration_minutes: int) -> List[str]:
    intro = (
        f"Merhaba arkadaşlar! Bugün {game_name} oyununu {platform} üzerinde "
        f"{style} ve {tone} bir bakış açısıyla ele alıyoruz."
    )
    segments = [
        "İlk olarak oyunun genel hissini konuşalım. Görsel tasarım, menü akışı ve ilk dakikalardaki izlenim çok önemli.",
        "Sonra kontrol sistemini ve oynanış akışını inceleyelim. Bu oyun gerçekten oyuncuyu sürece bağlayabiliyor mu?",
        "Ardından oyunun güçlü ve zayıf yönlerini konuşacağız. İster eğlence odaklı bir izleyici olun, ister detaycı bir oyuncu; herkes için net bir fikir oluşturacağız.",
        "Devamında en çok dikkat çeken anları ve en çok öne çıkan mekanikleri konuşacağız. Bunlar oyunun neden izlenmeye değer olduğunu belirleyen noktalar.",
        "Son olarak da sonuç çıkaracağız: Eğer bu oyunu alırdınız? Hangi tür oyuncular için daha uygun?",
    ]
    closing = (
        f"Kısacası, {game_name} oyununu {platform} üzerinde oynarken ne hissettiniz? Yorumlarda "
        "düşüncelerinizi yazın, bir sonraki videoda başka bir oyunu birlikte inceleyelim!"
    )
    return [intro, *segments, closing]


def build_youtube_metadata(game_name: str, platform: str, style: str, duration_minutes: int) -> Dict[str, Any]:
    title = f"{game_name} {platform} İncelemesi | {duration_minutes} Dakika {style} Oynanış"
    description = (
        f"{game_name} oyununun {platform} sürümünü deneyimledik. "
        f"Oynanış, grafikler, hikâye, zorluk seviyeleri ve genel öneri hakkındaki düşüncelerimizi paylaşıyoruz. "
        f"Bu video {style} bir anlatımla hazırlanmıştır."
    )
    tags = [
        game_name,
        platform,
        "oyun incelemesi",
        style,
        "youtube oyun videosu",
        "oyun analizi",
        "pc oyun",
    ]
    return {
        "title": title,
        "description": description,
        "tags": tags,
    }


def generate_workflow_output(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
    api_key: str | None = None,
) -> Dict[str, Any]:
    plan = generate_content_plan(
        game_name=game_name,
        platform=platform,
        style=style,
        tone=tone,
        duration_minutes=duration_minutes,
        api_key=api_key,
    )

    script_lines = build_script_lines(game_name, platform, tone, style, duration_minutes)
    meta = build_youtube_metadata(game_name, platform, style, duration_minutes)

    script_text = "\n\n".join(f"{idx}. {line}" for idx, line in enumerate(script_lines, start=1))
    youtube_meta_text = (
        f"Title: {meta['title']}\n\n"
        f"Description:\n{meta['description']}\n\n"
        f"Tags: {', '.join(meta['tags'])}"
    )

    return {
        "plan": plan,
        "script_lines": script_lines,
        "script_text": script_text,
        "youtube_meta": meta,
        "youtube_meta_text": youtube_meta_text,
    }


__all__ = ["build_script_lines", "build_youtube_metadata", "generate_workflow_output"]
