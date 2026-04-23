"""
Minimal sklearn-style text classification pipeline using OpenAI embeddings.

Course requirements covered:
- Supervised binary classification
- 75/25 train-test split
- Dimensionality reduction (PCA)
- Classification (Logistic Regression)
- Evaluation with common metrics

Expected CSV input:
- `text` column: raw text
- `label` column: binary labels (0/1 or two unique classes)

Usage example:
python ml_text_classification_outline.py \
  --csv-path /path/to/dataset.csv \
  --api-key "$OPENAI_API_KEY" \
  --save-plots
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from openai import OpenAI
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binary text classification with OpenAI embeddings + PCA.")
    parser.add_argument("--csv-path", required=True, help="Path to CSV file with `text` and `label` columns.")
    parser.add_argument("--api-key", default=None, help="OpenAI API key. Defaults to OPENAI_API_KEY env var.")
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model name.",
    )
    parser.add_argument("--test-size", type=float, default=0.25, help="Test split ratio. Default: 0.25")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed. Default: 42")
    parser.add_argument(
        "--pca-components",
        type=int,
        default=100,
        help="PCA components for classifier features. Default: 100",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size. Default: 64")
    parser.add_argument(
        "--cache-path",
        default=".embedding_cache.json",
        help="JSON cache path for embeddings. Default: .embedding_cache.json",
    )
    parser.add_argument(
        "--save-plots",
        action="store_true",
        help="Save confusion matrix and 2D PCA scatter plots as PNG files.",
    )
    return parser.parse_args()


def normalize_labels(label_series: pd.Series) -> np.ndarray:
    if label_series.nunique() != 2:
        raise ValueError("This script expects exactly 2 classes in the `label` column.")
    if set(label_series.unique()) <= {0, 1}:
        return label_series.astype(int).to_numpy()
    encoder = LabelEncoder()
    return encoder.fit_transform(label_series.astype(str))


def text_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}::{text}".encode("utf-8")).hexdigest()


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_cache(cache_path: Path) -> dict[str, list[float]]:
    if not cache_path.exists():
        return {}
    with cache_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache_path: Path, cache: dict[str, list[float]]) -> None:
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f)


def embed_texts(
    client: OpenAI,
    texts: list[str],
    model: str,
    batch_size: int,
    cache_path: Path,
) -> np.ndarray:
    cache = load_cache(cache_path)
    vectors: list[list[float]] = []

    missing = [t for t in texts if text_key(t, model) not in cache]
    if missing:
        for batch in chunked(missing, batch_size):
            response = client.embeddings.create(model=model, input=batch)
            for text, item in zip(batch, response.data):
                cache[text_key(text, model)] = item.embedding
        save_cache(cache_path, cache)

    for text in texts:
        vectors.append(cache[text_key(text, model)])
    return np.array(vectors, dtype=np.float32)


def maybe_save_plots(
    y_test: np.ndarray,
    y_pred: np.ndarray,
    x_test_pca_2d: np.ndarray,
    out_dir: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("Skipping plots: install matplotlib and seaborn to enable --save-plots")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("Confusion Matrix")
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(out_dir / "confusion_matrix.png", dpi=150)
    plt.close()

    plt.figure(figsize=(6, 5))
    plt.scatter(x_test_pca_2d[:, 0], x_test_pca_2d[:, 1], c=y_test, alpha=0.7)
    plt.title("2D PCA Projection (Test Set)")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.tight_layout()
    plt.savefig(out_dir / "pca_2d_scatter.png", dpi=150)
    plt.close()
    print(f"Saved plots to: {out_dir}")


def main() -> None:
    args = parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required_columns = {"text", "label"}
    if not required_columns.issubset(df.columns):
        raise ValueError("CSV must contain `text` and `label` columns.")

    df = df.dropna(subset=["text", "label"]).copy()
    df["text"] = df["text"].astype(str)
    y = normalize_labels(df["label"])
    x_text = df["text"].tolist()

    x_train_text, x_test_text, y_train, y_test = train_test_split(
        x_text,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y,
    )

    client = OpenAI(api_key=args.api_key)
    cache_path = Path(args.cache_path)

    x_train_embed = embed_texts(
        client=client,
        texts=x_train_text,
        model=args.embedding_model,
        batch_size=args.batch_size,
        cache_path=cache_path,
    )
    x_test_embed = embed_texts(
        client=client,
        texts=x_test_text,
        model=args.embedding_model,
        batch_size=args.batch_size,
        cache_path=cache_path,
    )

    max_components = min(x_train_embed.shape[1], x_train_embed.shape[0] - 1)
    pca_components = min(args.pca_components, max_components)
    if pca_components < 2:
        raise ValueError("Not enough data points for PCA. Add more samples.")

    pca = PCA(n_components=pca_components, random_state=args.random_state)
    x_train_reduced = pca.fit_transform(x_train_embed)
    x_test_reduced = pca.transform(x_test_embed)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(x_train_reduced, y_train)
    y_pred = clf.predict(x_test_reduced)
    y_prob = clf.predict_proba(x_test_reduced)[:, 1]

    print("=== Dataset ===")
    print(f"Total samples: {len(df)}")
    print(f"Train samples: {len(x_train_text)}")
    print(f"Test samples: {len(x_test_text)}")

    print("\n=== Features ===")
    print(f"Embedding shape (train): {x_train_embed.shape}")
    print(f"PCA components used: {pca_components}")
    print(f"Explained variance ratio sum: {pca.explained_variance_ratio_.sum():.4f}")

    print("\n=== Metrics (Test) ===")
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"Recall:    {recall_score(y_test, y_pred):.4f}")
    print(f"F1-score:  {f1_score(y_test, y_pred):.4f}")
    print(f"ROC-AUC:   {roc_auc_score(y_test, y_prob):.4f}")
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, digits=4))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    if args.save_plots:
        pca_2d = PCA(n_components=2, random_state=args.random_state)
        x_test_pca_2d = pca_2d.fit_transform(x_test_embed)
        maybe_save_plots(y_test, y_pred, x_test_pca_2d, out_dir=Path("ml_outputs"))


if __name__ == "__main__":
    main()
