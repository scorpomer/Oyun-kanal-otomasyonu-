import json
import sys
import types

import pytest

import app
from video_workflow import (
    build_youtube_metadata,
    generate_workflow_output,
    render_text_output,
    select_json_output,
)


def _workflow(api_key=None):
    return generate_workflow_output(
        game_name="Zelda",
        platform="Switch",
        style="eğlenceli ve hızlı",
        tone="heyecanlı",
        duration_minutes=8,
        api_key=api_key,
    )


def test_workflow_without_api_key_uses_local_fallback():
    workflow = _workflow()

    assert set(workflow) == {"plan", "script_lines", "script_text", "youtube_meta", "youtube_meta_text"}
    assert workflow["plan"]["title"].startswith("Zelda Switch")
    assert workflow["script_lines"][0].startswith("Merhaba arkadaşlar!")
    assert workflow["script_text"].startswith("1. ")
    assert "Başlık:" in workflow["youtube_meta_text"]
    json.dumps(workflow, ensure_ascii=False)


def test_metadata_tags_follow_platform():
    meta = build_youtube_metadata("Zelda", "Switch", "eğlenceli", 8)

    assert "Switch oyun" in meta["tags"]
    assert "pc oyun" not in meta["tags"]


@pytest.mark.parametrize(
    "mode, keys",
    [
        ("plan", {"plan"}),
        ("script", {"script_lines", "script_text"}),
        ("meta", {"youtube_meta", "youtube_meta_text"}),
        ("all", {"plan", "script_lines", "script_text", "youtube_meta", "youtube_meta_text"}),
    ],
)
def test_json_output_respects_mode(mode, keys):
    assert set(select_json_output(_workflow(), mode)) == keys


def test_text_output_modes():
    workflow = _workflow()

    assert render_text_output(workflow, "plan").startswith("# ")
    assert render_text_output(workflow, "script").startswith("1. Merhaba")
    assert render_text_output(workflow, "meta").startswith("Başlık:")
    assert render_text_output(workflow, "all").count("---") == 2


def _install_fake_genai(monkeypatch, text=None, error=None):
    calls = []

    class FakeModels:
        def generate_content(self, model, contents):
            calls.append(model)
            if error:
                raise error
            return types.SimpleNamespace(text=text)

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    google_pkg = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    genai_mod.Client = FakeClient
    google_pkg.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    return calls


def test_workflow_with_api_key_uses_gemini_plan(monkeypatch):
    calls = _install_fake_genai(
        monkeypatch,
        text='```json\n{"title": "Gemini başlığı", "hook": "Kanca", "outline": ["a", "b"]}\n```',
    )
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    plan = _workflow(api_key="test-anahtari")["plan"]

    assert calls == ["gemini-flash-latest"]
    assert plan["title"] == "Gemini başlığı"
    assert plan["outline"] == ["a", "b"]
    # Modelin döndürmediği alanlar yerel plandan tamamlanır.
    assert plan["shot_list"] and plan["cta"] and plan["seo_tags"]
    assert plan["platform"] == "Switch"


def test_gemini_model_can_be_overridden(monkeypatch):
    calls = _install_fake_genai(monkeypatch, text='{"title": "x"}')
    monkeypatch.setenv("GEMINI_MODEL", "baska-model")

    _workflow(api_key="test-anahtari")

    assert calls == ["baska-model"]


def test_gemini_error_falls_back_with_warning(monkeypatch, capsys):
    _install_fake_genai(monkeypatch, error=RuntimeError("404 model bulunamadı"))

    plan = _workflow(api_key="test-anahtari")["plan"]

    assert plan["title"].startswith("Zelda Switch")
    assert "yerel yedek plan" in capsys.readouterr().err


def test_cli_json_meta(monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(app, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["app.py", "--game", "Elden Ring", "--mode", "meta", "--output", "json"]
    )

    assert app.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"youtube_meta", "youtube_meta_text"}
    assert data["youtube_meta"]["tags"][0] == "Elden Ring"


def test_cli_rejects_invalid_duration(monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(app, "load_dotenv", lambda: None)
    monkeypatch.setattr(sys, "argv", ["app.py", "--game", "CS2", "--duration", "0"])

    assert app.main() == 2
    assert "en az 1 dakika" in capsys.readouterr().err
