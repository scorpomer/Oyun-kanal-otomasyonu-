#!/usr/bin/env python3

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from content_automation import generate_content_plan, render_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YouTube oyun kanalı için yapay zeka içerik otomasyonu."
    )
    parser.add_argument("--game", required=True, help="Oyun adı, örn. CS2, Zelda, Fortnite")
    parser.add_argument("--platform", default="PC", help="Platform, örn. PC, PS5, Xbox")
    parser.add_argument(
        "--style",
        default="eğlenceli ve hızlı",
        help="İçerik tonu / video stili",
    )
    parser.add_argument(
        "--tone",
        default="heyecanlı",
        help="Ses tonu, örn. eğlenceli, analitik, merak uyandırıcı",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=8,
        help="Video süresi (dakika)",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Çıktı formatı",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    api_key = os.getenv("GOOGLE_API_KEY")
    plan = generate_content_plan(
        game_name=args.game,
        platform=args.platform,
        style=args.style,
        tone=args.tone,
        duration_minutes=args.duration,
        api_key=api_key,
    )

    if args.output == "json":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    print(render_markdown(plan))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nİşlem kullanıcı tarafından iptal edildi.", file=sys.stderr)
        raise SystemExit(130)
