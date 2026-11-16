from video_workflow import (
    build_output,
    build_script_lines,
    build_youtube_metadata,
    generate_workflow_output,
    select_workflow_payload,
)


def test_build_script_lines_includes_intro_and_cta():
    lines = build_script_lines(
        game_name="Elden Ring",
        platform="PS5",
        tone="analitik",
        style="akıcı",
        duration_minutes=10,
    )
    assert len(lines) >= 3
    assert "Elden Ring" in lines[0]
    assert "PS5" in lines[0]
    assert "Yorumlarda" in lines[-1]


def test_build_youtube_metadata_contains_expected_fields():
    meta = build_youtube_metadata(
        game_name="Helldivers 2",
        platform="PC",
        style="eğlenceli",
        duration_minutes=8,
    )
    assert "Helldivers 2" in meta["title"]
    assert "PC" in meta["title"]
    assert meta["description"]
    assert "oyun incelemesi" in meta["tags"]


def test_generate_workflow_output_builds_text_blocks():
    output = generate_workflow_output(
        game_name="Stardew Valley",
        platform="PC",
        style="samimi",
        tone="sakin",
        duration_minutes=6,
        api_key=None,
    )
    assert output["plan"]["title"]
    assert output["script_lines"]
    assert output["script_text"].startswith("1.")
    assert "Title:" in output["youtube_meta_text"]


def test_build_output_supports_all_modes():
    common = {
        "game": "CS2",
        "platform": "PC",
        "style": "hızlı",
        "tone": "heyecanlı",
        "duration": 8,
        "api_key": None,
    }
    assert build_output(mode="plan", **common).startswith("# ")
    assert build_output(mode="script", **common).startswith("1.")
    assert build_output(mode="meta", **common).startswith("Title:")
    assert "\n\n---\n\n" in build_output(mode="all", **common)


def test_select_workflow_payload_respects_mode():
    workflow = generate_workflow_output(
        game_name="CS2",
        platform="PC",
        style="hızlı",
        tone="heyecanlı",
        duration_minutes=8,
        api_key=None,
    )
    assert set(select_workflow_payload(workflow, "plan").keys()) == {"plan"}
    assert set(select_workflow_payload(workflow, "script").keys()) == {"script_lines", "script_text"}
    assert set(select_workflow_payload(workflow, "meta").keys()) == {"youtube_meta", "youtube_meta_text"}
    assert set(select_workflow_payload(workflow, "all").keys()) == set(workflow.keys())
