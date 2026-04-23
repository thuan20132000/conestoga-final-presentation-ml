"""
Train classic ML classifiers for post-call analysis (category, sentiment, outcome).

Intended to be run from the repo root, e.g.:
  python ml/scripts/train_intent_model.py

Or via DVC: dvc repro
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "data" / "call_intent" / "training.csv"
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "post_call_models.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"


def _load_params() -> dict:
    params_file = REPO_ROOT / "params.yaml"
    if not params_file.is_file():
        return {
            "random_state": 42,
            "test_size": 0.2,
            "max_features": 5000,
            "ngram_max": 2,
        }
    import yaml  # PyYAML in requirements

    with open(params_file, encoding="utf-8") as f:
        full = yaml.safe_load(f) or {}
    return full.get("train_intent", {})


def _build_pipeline(p: dict) -> Pipeline:
    ngram = (1, int(p.get("ngram_max", 2)))
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=int(p.get("max_features", 5000)),
                    ngram_range=ngram,
                ),
            ),
            ("clf", LogisticRegression(max_iter=int(p.get("max_iter", 500)))),
        ]
    )


def main() -> int:
    p = _load_params()
    if not DATA_PATH.exists():
        print(f"Missing training data: {DATA_PATH}", file=sys.stderr)
        return 1

    df = pd.read_csv(DATA_PATH)
    for col in ("text", "category", "sentiment", "outcome"):
        if col not in df.columns:
            print(f"CSV must include column: {col}", file=sys.stderr)
            return 1

    X = df["text"].astype(str)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    models: dict = {}
    metrics: dict = {}
    n = len(df)
    test_size = float(p.get("test_size", 0.2))
    random_state = int(p.get("random_state", 42))

    for target in ("category", "sentiment", "outcome"):
        y = df[target].astype(str)
        if n < 4:
            pipe = _build_pipeline(p)
            pipe.fit(X, y)
            pred = pipe.predict(X)
            report = classification_report(y, pred, output_dict=True, zero_division=0)
        else:
            strat = y if y.value_counts().min() >= 2 and n >= 8 else None
            try:
                X_train, X_test, y_train, y_test = train_test_split(
                    X,
                    y,
                    test_size=test_size,
                    random_state=random_state,
                    stratify=strat,
                )
            except ValueError:
                # e.g. too many classes for small test set — fit on a simple random split
                X_train, X_test, y_train, y_test = train_test_split(
                    X,
                    y,
                    test_size=test_size,
                    random_state=random_state,
                    stratify=None,
                )
            if len(X_test) == 0:
                X_train, X_test, y_train, y_test = X, X, y, y
            pipe = _build_pipeline(p)
            pipe.fit(X_train, y_train)
            pred = pipe.predict(X_test)
            report = classification_report(y_test, pred, output_dict=True, zero_division=0)
        models[target] = pipe
        metrics[target] = report

    joblib.dump(models, MODEL_PATH)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Wrote {MODEL_PATH}")
    print(f"Wrote {METRICS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
