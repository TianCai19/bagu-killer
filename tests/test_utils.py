from datetime import UTC, datetime

from ai_offer_catcher.utils import (
    build_window_key,
    compact_text,
    extract_first_json_object,
    fingerprint_text,
    normalize_question,
    parse_cli_datetime,
)


def test_extract_first_json_object_handles_wrapped_text():
    payload = extract_first_json_object("```json\n{\"a\": 1}\n```")
    assert payload == {"a": 1}


def test_normalize_question_removes_prefix_and_normalizes_case():
    assert normalize_question("1. 什么是 Agent Memory？") == "什么是 agent memory"


def test_fingerprint_is_stable():
    assert fingerprint_text("abc") == fingerprint_text("abc")


def test_compact_text_skips_empty_parts():
    assert compact_text(["标题", "", None, "正文"]) == "标题\n\n正文"


def test_parse_cli_datetime_supports_date_only():
    assert parse_cli_datetime("2025-01-20") == datetime(2025, 1, 20, 0, 0, tzinfo=UTC)


def test_build_window_key_is_stable():
    value = build_window_key(datetime(2025, 1, 20, 0, 0, tzinfo=UTC), None)
    assert value.startswith("2025-01-20T00:00:00+00:00__open")
