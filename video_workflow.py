#!/usr/bin/env python3
"""İçerik paketini metin/JSON çıktısına dönüştürür ve dosyalara kaydeder."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from content_automation import (
    build_local_metadata,
    build_local_script,
    generate_content_package,
    render_markdown,
)

MODES = ("plan", "script", "meta", "thumbnail", "shorts", "all")
SEPARATOR = "\n\n---\n\n"


def build_script_lines(game_name: str, platform: str, tone: str, style: str, duration_minutes: int) -> List[str]:
    """Geriye uyumluluk için: yerel video metnini paragraf listesi olarak döndürür."""
    return [section["text"] for section in build_local_script(game_name, platform, style, tone, duration_minutes)]


def build_youtube_metadata(game_name: str, platform: str, style: str, duration_minutes: int) -> Dict[str, Any]:
    """Geriye uyumluluk için: yerel YouTube bilgilerini döndürür."""
    return build_local_metadata(game_name, platform, style, duration_minutes)


def format_script(sections: List[Dict[str, Any]]) -> str:
    blocks = []
    for index, section in enumerate(sections, start=1):
        start = f"[{section['start']}] " if section.get("start") else ""
        target = f" (~{section['target_words']} kelime)" if section.get("target_words") else ""
        blocks.append(f"{index}. {start}{section['title']}{target}\n{section['text']}")
    return "\n\n".join(blocks)


def format_youtube_meta(meta: Dict[str, Any], sections: List[Dict[str, Any]]) -> str:
    chapters = "\n".join(f"{s['start']} {s['title']}" for s in sections if s.get("start"))
    description = meta["description"]
    if chapters and "0:00" not in description:
        description += f"\n\nBölümler:\n{chapters}"
    return f"Başlık: {meta['title']}\n\nAçıklama:\n{description}\n\nEtiketler: {', '.join(meta['tags'])}"


def format_thumbnail(thumbnail: Dict[str, Any]) -> str:
    return (
        f"Kapak yazısı: {thumbnail['text']}\n\n"
        f"Tasarım: {thumbnail['visual']}\n\n"
        f"Görsel üretim istemi (prompt):\n{thumbnail['prompt']}"
    )


def format_shorts(shorts: Dict[str, Any]) -> str:
    beats = "\n\n".join(
        f"[{beat['time']}] {beat['voice']}" + (f"\n  Ekran yazısı: {beat['on_screen']}" if beat.get("on_screen") else "")
        for beat in shorts["beats"]
    )
    return f"Shorts başlığı: {shorts['title']}\n\nAçıklama: {shorts['description']}\n\n{beats}"


def generate_workflow_output(
    game_name: str,
    platform: str,
    style: str,
    tone: str,
    duration_minutes: int,
    api_key: str | None = None,
    channel: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    package = generate_content_package(
        game_name=game_name,
        platform=platform,
        style=style,
        tone=tone,
        duration_minutes=duration_minutes,
        api_key=api_key,
        channel=channel,
    )
    sections = package["script"]
    return {
        "game": game_name,
        "plan": package["plan"],
        "script_sections": sections,
        "script_lines": [section["text"] for section in sections],
        "script_text": format_script(sections),
        "youtube_meta": package["youtube"],
        "youtube_meta_text": format_youtube_meta(package["youtube"], sections),
        "thumbnail": package["thumbnail"],
        "thumbnail_text": format_thumbnail(package["thumbnail"]),
        "shorts": package["shorts"],
        "shorts_text": format_shorts(package["shorts"]),
        "sources": package["sources"],
    }


def select_json_output(workflow: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """JSON çıktısında yalnızca --mode ile istenen bölümü döndürür."""
    if mode == "plan":
        return {"plan": workflow["plan"]}
    if mode == "script":
        return {key: workflow[key] for key in ("script_sections", "script_lines", "script_text")}
    if mode == "meta":
        return {"youtube_meta": workflow["youtube_meta"], "youtube_meta_text": workflow["youtube_meta_text"]}
    if mode == "thumbnail":
        return {"thumbnail": workflow["thumbnail"], "thumbnail_text": workflow["thumbnail_text"]}
    if mode == "shorts":
        return {"shorts": workflow["shorts"], "shorts_text": workflow["shorts_text"]}
    return workflow


def render_text_output(workflow: Dict[str, Any], mode: str) -> str:
    """Metin çıktısında --mode ile istenen bölümü döndürür."""
    parts = {
        "plan": render_markdown(workflow["plan"]),
        "script": workflow["script_text"],
        "meta": workflow["youtube_meta_text"],
        "thumbnail": workflow["thumbnail_text"],
        "shorts": workflow["shorts_text"],
    }
    if mode in parts:
        return parts[mode]
    return SEPARATOR.join(parts.values())


def _slug(value: str) -> str:
    slug = re.sub(r"[^\w.-]+", "-", value.strip(), flags=re.UNICODE).strip("-.").lower()
    return slug or "video"


def save_package(workflow: Dict[str, Any], output_dir: str | Path) -> Path:
    """Paketi output_dir/<oyun>-<zaman>/ klasörüne ayrı dosyalar halinde kaydeder."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = Path(output_dir) / f"{_slug(workflow['game'])}-{timestamp}"
    target.mkdir(parents=True, exist_ok=False)
    files = {
        "plan.md": render_markdown(workflow["plan"]),
        "video_metni.txt": workflow["script_text"],
        "youtube_bilgileri.txt": workflow["youtube_meta_text"],
        "kapak.txt": workflow["thumbnail_text"],
        "shorts.txt": workflow["shorts_text"],
        "paket.json": json.dumps(workflow, ensure_ascii=False, indent=2),
    }
    for name, content in files.items():
        (target / name).write_text(content.rstrip() + "\n", encoding="utf-8")
    return target


def main() -> int:
    from app import main as app_main

    return app_main(default_mode="all")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MODES",
    "build_script_lines",
    "build_youtube_metadata",
    "generate_workflow_output",
    "render_text_output",
    "save_package",
    "select_json_output",
]
