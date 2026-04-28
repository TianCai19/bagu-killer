from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader


def build_prompt_renderer(prompt_dir: Path) -> Environment:
    return Environment(loader=FileSystemLoader(str(prompt_dir)), autoescape=False)


def render_prompt(env: Environment, template_name: str, **kwargs: Any) -> str:
    template = env.get_template(template_name)
    return template.render(**kwargs).strip()


def extract_first_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    
    # Fast path: if the model respected the prompt and output pure JSON
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Attempt to extract markdown json blocks first (more reliable if it exists)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Robust fallback: find the last complete JSON block in the text (often models think first, then output JSON)
    # Match everything between { and }, handling nested structures by finding the widest possible match
    match = re.search(r"(\{.*\})", text, re.S)
    if not match:
        raise ValueError("No valid JSON object found in text")
    
    json_str = match.group(1)
    
    # If the JSON string is truncated, try to fix it by adding closing brackets
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Check if the string ends abruptly and might be fixable (very basic heuristic)
        if "Expecting value" in str(e) or "Unterminated string" in str(e) or "Expecting property name enclosed in double quotes" in str(e):
            raise ValueError(f"Extracted JSON block appears to be truncated: {e}")
        raise ValueError(f"Failed to parse extracted JSON block: {e}")


def normalize_question(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[\s\d一二三四五六七八九十\.\-、（）()]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[？?]+$", "", cleaned)
    cleaned = cleaned.replace("Agent", "agent").replace("RAG", "rag")
    cleaned = cleaned.replace("Tool Calling", "tool calling").replace("Memory", "memory")
    return cleaned.strip().lower()


def fingerprint_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def compact_text(parts: Iterable[str | None]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_xhs_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    if ts > 10_000_000_000:
        ts = ts // 1000
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def parse_cli_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) == 10:
        return datetime.fromisoformat(cleaned + "T00:00:00").replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_window_key(date_from: datetime | None, date_to: datetime | None) -> str:
    start = date_from.astimezone(UTC).isoformat() if date_from else "open"
    end = date_to.astimezone(UTC).isoformat() if date_to else "open"
    return f"{start}__{end}"


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
