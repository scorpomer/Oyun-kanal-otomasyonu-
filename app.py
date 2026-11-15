#!/usr/bin/env python3

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from video_workflow import generate_workflow_output, render_text_output, select_json_output


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
    parser.add_argument(
        "--mode",
        choices=["plan", "script", "meta", "all"],
        default="plan",
        help="Üretilecek içerik tipi",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    api_key = os.getenv("GOOGLE_API_KEY")
    try:
        workflow = generate_workflow_output(
            game_name=args.game,
            platform=args.platform,
            style=args.style,
            tone=args.tone,
            duration_minutes=args.duration,
            api_key=api_key,
        )
    except ValueError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2

    if args.output == "json":
        print(json.dumps(select_json_output(workflow, args.mode), ensure_ascii=False, indent=2))
    else:
        print(render_text_output(workflow, args.mode))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nİşlem kullanıcı tarafından iptal edildi.", file=sys.stderr)
        raise SystemExit(130)
