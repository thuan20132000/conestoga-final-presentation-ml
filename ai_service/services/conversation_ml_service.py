"""Post-call analysis with sklearn pipelines trained via DVC (see ml/scripts/, dvc.yaml)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib

from ai_service.config import settings

logger = logging.getLogger(__name__)

_repo_root = Path(__file__).resolve().parents[2]
_models_cache: Optional[dict] = None
_model_mtime: Optional[float] = None


def _resolve_model_path() -> Path:
    raw = (settings.call_ml_model_path or "ml/artifacts/post_call_models.joblib").strip()
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return _repo_root / path


def _get_models() -> dict:
    global _models_cache, _model_mtime
    path = _resolve_model_path()
    if not path.is_file():
        raise FileNotFoundError(f"ML model file not found: {path}")
    mtime = path.stat().st_mtime
    if _models_cache is not None and _model_mtime == mtime:
        return _models_cache
    _models_cache = joblib.load(path)
    _model_mtime = mtime
    if not isinstance(_models_cache, dict) or not all(
        k in _models_cache for k in ("category", "sentiment", "outcome")
    ):
        raise ValueError("post_call_models.joblib must be a dict with category, sentiment, outcome pipelines")
    return _models_cache


def conversation_to_text(conversation: List[Dict[str, Any]]) -> str:
    """Flatten transcript to one string for TF-IDF (matches training format)."""
    parts: list[str] = []
    for msg in conversation:
        role = str(msg.get("role", "user"))
        content = (msg.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _fallback_summary(conversation: List[Dict[str, Any]]) -> str:
    user_bits = [str(m.get("content", "")).strip() for m in conversation if m.get("role") == "user" and m.get("content")]
    joined = " ".join(user_bits)
    if not joined:
        return "No caller content recorded."
    return joined[:500] + ("…" if len(joined) > 500 else "")


def analyze_conversation_ml(conversation: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Predict outcome, sentiment, and category; summary is extractive (no LLM).
    Return shape matches OpenAIService.analyze_conversation.
    """
    text = conversation_to_text(conversation)
    if not text.strip():
        return {
            "outcome": "unknown",
            "sentiment": "neutral",
            "category": "unknown",
            "summary": "No transcript available.",
        }

    models = _get_models()
    row = [text]
    category = str(models["category"].predict(row)[0])
    sentiment = str(models["sentiment"].predict(row)[0])
    outcome = str(models["outcome"].predict(row)[0])
    return {
        "outcome": outcome,
        "sentiment": sentiment,
        "category": category,
        "summary": _fallback_summary(conversation),
    }
