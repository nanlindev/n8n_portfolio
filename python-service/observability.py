import hashlib
import json
from typing import Any

LLM_CONTENT_LIMIT = 3000
METADATA_PREVIEW_LIMIT = 200
SUMMARY_PREVIEW_LIMIT = 300


def preview(text: str | None, n: int = METADATA_PREVIEW_LIMIT) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def content_hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def truncate_for_llm(content: str | None, limit: int = LLM_CONTENT_LIMIT) -> tuple[str, bool]:
    content = content or ""
    if len(content) <= limit:
        return content, False
    return content[:limit], True


def build_trace_input(
    *,
    source_url: str | None,
    title: str,
    content: str | None,
) -> dict[str, Any]:
    return {
        "source_url": source_url,
        "title": title,
        "content_preview": preview(content),
        "content_length": len(content or ""),
    }


def build_trace_output(result: dict[str, Any], confidence: str) -> dict[str, Any]:
    tags = result.get("tags") or {}
    summary = result.get("summary") or {}
    category_display = result.get("category_display") or {}
    keywords_en = tags.get("en", []) if isinstance(tags, dict) else []
    keywords_zh = tags.get("zh", []) if isinstance(tags, dict) else []

    return {
        "category_key": result.get("category_key"),
        "category_display_zh": category_display.get("zh"),
        "priority": result.get("priority"),
        "sentiment": result.get("sentiment"),
        "summary_zh": preview(summary.get("zh", ""), SUMMARY_PREVIEW_LIMIT),
        "summary_en": preview(summary.get("en", ""), SUMMARY_PREVIEW_LIMIT),
        "keywords_en": keywords_en[:5],
        "keywords_zh": keywords_zh[:5],
        "validation_confidence": confidence,
    }


def build_propagate_metadata(
    *,
    source_url: str | None,
    title: str,
    content: str | None,
    truncated: bool,
    prompt_version: str,
    prompt_hash_value: str,
    model: str,
) -> dict[str, str]:
    return {
        "source_url": preview(source_url, METADATA_PREVIEW_LIMIT),
        "title_preview": preview(title, 120),
        "content_length": str(len(content or "")),
        "content_hash": content_hash(content),
        "content_truncated": str(truncated).lower(),
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash_value,
        "model": model,
    }


def build_failed_trace_output(error_type: str, error_stage: str) -> dict[str, str]:
    return {
        "status": "failed",
        "error_type": error_type,
        "error_stage": error_stage,
    }


def classify_exception(exc: Exception) -> tuple[str, str, int]:
    if isinstance(exc, json.JSONDecodeError):
        return "json_parse_error", "parse", 502
    if isinstance(exc, ValueError) and "Empty response" in str(exc):
        return "empty_response", "llm_call", 502
    if "status_code" in dir(exc):
        return "provider_error", "llm_call", 502
    return "internal_error", "unknown", 500
