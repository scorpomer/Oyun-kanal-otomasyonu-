import json

from content_automation import build_local_plan


def test_build_local_plan_has_expected_fields():
    plan = build_local_plan(
        game_name="Helldivers 2",
        platform="PC",
        style="eğlenceli ve hızlı",
        tone="heyecanlı",
        duration_minutes=8,
    )

    assert plan["title"]
    assert plan["hook"]
    assert plan["outline"]
    assert plan["shot_list"]
    assert plan["cta"]
    assert plan["seo_tags"][0] == "Helldivers 2"


def test_build_local_plan_is_json_serializable():
    plan = build_local_plan(
        game_name="Stardew Valley",
        platform="PC",
        style="sakin ve keyifli",
        tone="samimi",
        duration_minutes=6,
    )

    serialized = json.dumps(plan, ensure_ascii=False)
    assert "Stardew Valley" in serialized


def test_extract_json_payload_handles_fences_and_surrounding_text():
    from content_automation import _extract_json_payload

    assert _extract_json_payload('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json_payload('İşte plan: {"a": 2} umarım beğenirsin') == {"a": 2}


def test_generate_content_plan_validates_input():
    import pytest

    from content_automation import generate_content_plan

    with pytest.raises(ValueError):
        generate_content_plan("  ", "PC", "stil", "ton", 8)
    with pytest.raises(ValueError):
        generate_content_plan("CS2", "PC", "stil", "ton", 0)
