#!/usr/bin/env python3
"""Shared helpers for style-decisions.json management."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STYLE_DECISIONS = PROJECT_ROOT / "style-decisions.json"
DEFAULT_STYLE_DECISIONS_SCHEMA = PROJECT_ROOT / "style-decisions.schema.json"

TRANSLATION_MODE_OPTIONS = {
    "full": {
        "name": "全文翻譯",
        "description": "完整翻譯所有內容，保留原文結構與細節",
    },
    "summary": {
        "name": "摘要翻譯",
        "description": "精簡翻譯，提取重點規則，省略範例與冗長說明",
    },
    "bilingual": {
        "name": "雙語模式",
        "description": "中文翻譯為主，英文原文以 blockquote 附於每段之後",
    },
}

DEFAULT_STYLE_DECISIONS_PAYLOAD = {
    "_meta": {
        "description": "風格決定記錄 - 翻譯用語選擇與原因",
        "updated": "",
    },
    "translation_mode": {
        "mode": "full",
        "options": TRANSLATION_MODE_OPTIONS,
        "reason": "預設使用全文翻譯，可視需要改為摘要翻譯。",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_style_decisions_payload() -> dict[str, Any]:
    return deepcopy(DEFAULT_STYLE_DECISIONS_PAYLOAD)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_style_decisions_schema(path: Path = DEFAULT_STYLE_DECISIONS_SCHEMA) -> dict[str, Any] | None:
    return load_json(path, None)


def validate_style_decisions_payload(
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    formatted: list[str] = []
    for error in errors:
        path = ".".join(str(part) for part in error.path) or "<root>"
        formatted.append(f"{path}: {error.message}")
    return formatted


def ensure_meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.setdefault("_meta", {})
    if not isinstance(meta, dict):
        payload["_meta"] = meta = {}
    meta.setdefault("description", DEFAULT_STYLE_DECISIONS_PAYLOAD["_meta"]["description"])
    meta.setdefault("updated", "")
    return payload


def deep_merge(base: Any, patch: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(patch, dict):
        return deepcopy(patch)

    merged = deepcopy(base)
    for key, value in patch.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_style_decisions(
    path: Path = DEFAULT_STYLE_DECISIONS,
    *,
    default: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload = load_json(path, None)
    if payload is None:
        return deepcopy(default) if default is not None else None
    return payload


def save_style_decisions(
    path: Path,
    payload: dict[str, Any],
    *,
    schema_path: Path = DEFAULT_STYLE_DECISIONS_SCHEMA,
    touch_timestamp: bool = True,
) -> dict[str, Any]:
    schema = load_style_decisions_schema(schema_path)
    if schema is None:
        raise ValueError(f"Schema file not found: {schema_path}")

    normalized = deepcopy(payload)
    ensure_meta(normalized)
    if touch_timestamp:
        normalized["_meta"]["updated"] = utc_now_iso()

    errors = validate_style_decisions_payload(normalized, schema)
    if errors:
        raise ValueError("\n".join(errors))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def load_and_validate_style_decisions(
    path: Path = DEFAULT_STYLE_DECISIONS,
    *,
    schema_path: Path = DEFAULT_STYLE_DECISIONS_SCHEMA,
) -> dict[str, Any]:
    payload = load_style_decisions(path, default=default_style_decisions_payload())
    assert payload is not None
    schema = load_style_decisions_schema(schema_path)
    if schema is None:
        raise ValueError(f"Schema file not found: {schema_path}")
    errors = validate_style_decisions_payload(payload, schema)
    if errors:
        raise ValueError("\n".join(errors))
    return payload
