import json
import sys
import types

import pytest

import app
from content_automation import DEFAULT_CHANNEL, build_local_script, load_channel_profile
from video_workflow import (
    build_youtube_metadata,
    generate_workflow_output,
    render_text_output,
    save_package,
    select_json_output,
)

ALL_KEYS = {
    "game", "plan", "script_sections", "script_lines", "script_text",
    "youtube_meta", "youtube_meta_text", "thumbnail", "thumbnail_text",
    "shorts", "shorts_text", "sources",
}


def _workflow(api_key=None, duration=8, channel=None):
    return generate_workflow_output(
        game_name="Zelda",
        platform="Switch",
        style="eğlenceli ve hızlı",
        tone="heyecanlı",
        duration_minutes=duration,
        api_key=api_key,
        channel=channel or DEFAULT_CHANNEL,
    )


def test_workflow_without_api_key_uses_local_templates():
    workflow = _workflow()

    assert set(workflow) == ALL_KEYS
    assert set(workflow["sources"].values()) == {"yerel şablon"}
    assert workflow["plan"]["title"].startswith("Zelda Switch")
    assert workflow["script_lines"][0].startswith("Merhaba arkadaşlar!")
    assert workflow["script_text"].startswith("1. [0:00] Açılış")
    assert "Başlık:" in workflow["youtube_meta_text"]
    assert "Bölümler:\n0:00 Açılış" in workflow["youtube_meta_text"]
    assert "ZELDA" in workflow["thumbnail"]["text"]
    assert "#shorts" in workflow["shorts"]["title"]
    json.dumps(workflow, ensure_ascii=False)


@pytest.mark.parametrize("minutes", [1, 3, 8, 20])
def test_script_scales_with_duration(minutes):
    sections = build_local_script("Hades", "PC", "hızlı", "enerjik", minutes)

    assert sections[0]["start"] == "0:00"
    last_minute, last_second = map(int, sections[-1]["start"].split(":"))
    assert last_minute * 60 + last_second < minutes * 60
    total_words = sum(section["target_words"] for section in sections)
    assert abs(total_words - minutes * 140) <= len(sections)


def test_longer_videos_have_more_sections():
    short = build_local_script("Hades", "PC", "hızlı", "enerjik", 3)
    long = build_local_script("Hades", "PC", "hızlı", "enerjik", 12)

    assert len(long) > len(short)


def test_channel_profile_is_used(tmp_path):
    profile = tmp_path / "kanal.json"
    profile.write_text(
        json.dumps(
            {"kanal_adi": "Piksel Kulübü", "sunucu": {"ad": "Nova", "selamlama": "Selam oyuncular!"}, "sabit_etiketler": ["piksel"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    channel = load_channel_profile(profile)
    workflow = _workflow(channel=channel)

    assert channel["sunucu"]["kapanis"] == DEFAULT_CHANNEL["sunucu"]["kapanis"]  # eksik alan varsayılandan gelir
    assert workflow["script_lines"][0].startswith("Selam oyuncular! Ben Nova, burası Piksel Kulübü!")
    assert "piksel" in workflow["youtube_meta"]["tags"]


def test_broken_channel_file_falls_back(tmp_path, capsys):
    profile = tmp_path / "kanal.json"
    profile.write_text("{bozuk", encoding="utf-8")

    assert load_channel_profile(profile) == DEFAULT_CHANNEL
    assert "kanal dosyası okunamadı" in capsys.readouterr().err


def test_metadata_tags_follow_platform():
    meta = build_youtube_metadata("Zelda", "Switch", "eğlenceli", 8)

    assert "Switch oyun" in meta["tags"]
    assert "pc oyun" not in meta["tags"]


@pytest.mark.parametrize(
    "mode, keys",
    [
        ("plan", {"plan"}),
        ("script", {"script_sections", "script_lines", "script_text"}),
        ("meta", {"youtube_meta", "youtube_meta_text"}),
        ("thumbnail", {"thumbnail", "thumbnail_text"}),
        ("shorts", {"shorts", "shorts_text"}),
        ("all", ALL_KEYS),
    ],
)
def test_json_output_respects_mode(mode, keys):
    assert set(select_json_output(_workflow(), mode)) == keys


def test_text_output_modes():
    workflow = _workflow()

    assert render_text_output(workflow, "plan").startswith("# ")
    assert render_text_output(workflow, "script").startswith("1. [0:00]")
    assert render_text_output(workflow, "meta").startswith("Başlık:")
    assert render_text_output(workflow, "thumbnail").startswith("Kapak yazısı:")
    assert render_text_output(workflow, "shorts").startswith("Shorts başlığı:")
    assert render_text_output(workflow, "all").count("\n---\n") == 4


def test_save_package_writes_all_files(tmp_path):
    target = save_package(_workflow(), tmp_path)

    names = sorted(path.name for path in target.iterdir())
    assert names == ["kapak.txt", "paket.json", "plan.md", "shorts.txt", "video_metni.txt", "youtube_bilgileri.txt"]
    assert target.name.startswith("zelda-")
    assert json.loads((target / "paket.json").read_text(encoding="utf-8"))["game"] == "Zelda"


# ---------------------------------------------------------------------------
# Gemini yolu (gerçek ağ çağrısı yapılmaz; istemci taklit edilir)
# ---------------------------------------------------------------------------

def _install_fake_genai(monkeypatch, text=None, error=None):
    calls = []

    class FakeModels:
        def generate_content(self, model, contents, config=None):
            calls.append({"model": model, "prompt": contents, "config": config})
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


FULL_RESPONSE = {
    "plan": {"title": "Gemini başlığı", "hook": "Kanca", "outline": ["a", "b"]},
    "script": [
        {"title": "Giriş", "start": "0:00", "text": "Selam!"},
        {"title": "Final", "start": "7:00", "text": "Görüşürüz."},
    ],
    "youtube": {"title": "YT başlık", "description": "YT açıklama", "tags": ["x", "y"]},
    "thumbnail": {"text": "WOW", "visual": "görsel", "prompt": "istem"},
    "shorts": {"title": "Kısa #shorts", "beats": [{"time": "0-3 sn", "voice": "Bak!", "on_screen": "BAK"}]},
}


def test_workflow_with_api_key_uses_gemini_for_all_parts(monkeypatch):
    calls = _install_fake_genai(monkeypatch, text="```json\n" + json.dumps(FULL_RESPONSE, ensure_ascii=False) + "\n```")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    workflow = _workflow(api_key="test-anahtari")

    assert len(calls) == 1
    assert calls[0]["model"] == "gemini-flash-latest"
    assert "Kaptan" in calls[0]["prompt"]  # kanal karakteri isteme ekleniyor
    assert set(workflow["sources"].values()) == {"Gemini"}
    plan = workflow["plan"]
    assert plan["title"] == "Gemini başlığı"
    assert plan["outline"] == ["a", "b"]
    assert plan["shot_list"] and plan["cta"] and plan["seo_tags"]  # eksikler yerelden
    assert plan["platform"] == "Switch"
    assert workflow["script_lines"] == ["Selam!", "Görüşürüz."]
    assert workflow["youtube_meta"]["title"] == "YT başlık"
    assert workflow["thumbnail"]["text"] == "WOW"
    assert workflow["shorts"]["beats"][0]["voice"] == "Bak!"
    assert workflow["shorts"]["description"]  # eksik açıklama yerelden


def test_partial_gemini_response_falls_back_per_part(monkeypatch):
    _install_fake_genai(monkeypatch, text=json.dumps({"plan": {"title": "Sadece plan"}, "script": "hatalı"}))

    workflow = _workflow(api_key="test-anahtari")

    assert workflow["sources"]["plan"] == "Gemini"
    assert workflow["sources"]["script"] == "yerel şablon"
    assert workflow["script_lines"][0].startswith("Merhaba arkadaşlar!")


def test_gemini_model_can_be_overridden(monkeypatch):
    calls = _install_fake_genai(monkeypatch, text=json.dumps({"plan": {"title": "x"}}))
    monkeypatch.setenv("GEMINI_MODEL", "baska-model")

    _workflow(api_key="test-anahtari")

    assert calls[0]["model"] == "baska-model"


@pytest.mark.parametrize("kwargs", [{"error": RuntimeError("404 model bulunamadı")}, {"text": "{}"}])
def test_gemini_failure_falls_back_with_warning(monkeypatch, capsys, kwargs):
    _install_fake_genai(monkeypatch, **kwargs)

    workflow = _workflow(api_key="test-anahtari")

    assert workflow["plan"]["title"].startswith("Zelda Switch")
    assert set(workflow["sources"].values()) == {"yerel şablon"}
    assert "yerel şablonlar kullanılıyor" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Komut satırı
# ---------------------------------------------------------------------------

@pytest.fixture
def cli(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(app, "load_dotenv", lambda: None)


def test_cli_json_meta_without_saving(cli, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert app.main(["--game", "Elden Ring", "--mode", "meta", "--output", "json", "--no-save"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"youtube_meta", "youtube_meta_text"}
    assert data["youtube_meta"]["tags"][0] == "Elden Ring"
    assert not (tmp_path / "output").exists()


def test_cli_saves_package_by_default(cli, capsys, tmp_path):
    assert app.main(["--game", "Hades", "--mode", "shorts", "--output-dir", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Shorts başlığı:")
    assert "İçerik paketi kaydedildi" in captured.err
    assert len(list(tmp_path.iterdir())) == 1


def test_cli_rejects_invalid_duration(cli, capsys):
    assert app.main(["--game", "CS2", "--duration", "0", "--no-save"]) == 2
    assert "en az 1 dakika" in capsys.readouterr().err
