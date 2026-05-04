"""
Train Headline Classifier

This script trains a model to distinguish between:
- Label 0: General news articles
- Label 1: Fact-check / verification articles
"""

import sys
import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

def main():
    # Folder Path
    backend_dir = Path(__file__).parent
    dataset_path = backend_dir / "dataset.csv"
    model_path = backend_dir / "model.pkl"
    metrics_path = backend_dir / "train_model_metrics.json"

    if not dataset_path.exists():
        print(f"[ERROR] dataset.csv not found at {dataset_path}")
        print("Please ensure dataset.csv is in the backend directory.")
        sys.exit(1)

    print("-" * 70)
    print("Fake News Checkmate - Headline Classifier Training")
    print("-" * 70)
    print()

    # Load dataset
    print(f"Loading dataset from {dataset_path}")
    try:
        df = pd.read_csv(dataset_path)
    except Exception as e:
        print(f"[ERROR] Error loading dataset: {e}")
        sys.exit(1)

    # Validate
    if "news" not in df.columns or "label" not in df.columns:
        print("[ERROR] Error: dataset.csv must have 'news' and 'label' columns")
        print(f"Found columns: {list(df.columns)}")
        sys.exit(1)

    # Clean Data
    df = df.dropna(subset=["news"])
    df["news"] = df["news"].astype(str).str.strip()
    df = df[df["news"] != ""]

    if df.empty:
        print("[ERROR] dataset contains no valid news headlines after cleaning.")
        sys.exit(1)

    print(f"[OK] Loaded {len(df)} samples")
    print(f"   - Label 0 (General News): {(df['label'] == 0).sum()} samples")
    print(f"   - Label 1 (Fact-check): {(df['label'] == 1).sum()} samples")
    print()

    # Prepare data
    X = df["news"].tolist()
    y = df["label"].tolist()

    # Split data
    print("Splitting data (80% train, 20% test).")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Training stats
    print(f"    - Training samples: {len(X_train)}")
    train_counts = pd.Series(y_train).value_counts().sort_index()
    for label, count in train_counts.items():
        pct = (count / len(y_train)) * 100
        label_name = "General News" if label == 0 else "Fact-check"
        print(f"       Label {label} ({label_name}): {count} samples ({pct:.2f}%)")
    print()

    # Test stats
    print(f"    - Test samples: {len(X_test)}")
    test_counts = pd.Series(y_test).value_counts().sort_index()
    for label, count in test_counts.items():
        pct = (count / len(y_test)) * 100
        label_name = "General News" if label == 0 else "Fact-check"
        print(f"       Label {label} ({label_name}): {count} samples ({pct:.2f}%)")
    print()

    # Build pipeline
    print("Build model pipeline...")
    print("   - Vectorizer: TfidfVectorizer (1-3 n-grams)")
    print("   - Classifier: LogisticRegression (max_iter=1000)")

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=10000,
            min_df=2,
            stop_words="english",
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight="balanced",
        )),
    ])
    print()

    # Train model
    print("Training model...")
    try:
        pipeline.fit(X_train, y_train)
        print("Training completed")
    except Exception as e:
        print(f"Error during training: {e}")
        sys.exit(1)
    print()

    # Evaluate on test set
    print("Evaluating on test set...")
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    report_dict = classification_report(
        y_test,
        y_pred,
        target_names=["General News", "Fact-Check"],
        digits=3,
        output_dict=True
    )

    report_text = classification_report(
        y_test,
        y_pred,
        target_names=["General News", "Fact-Check"],
        digits=3
    )

    print(f"   Accuracy: {accuracy:.2%}")
    print()
    print("Classification Report:")
    print("-" * 60)
    print(report_text)
    print()

    # Save model
    print(f"Saving model to {model_path}...")
    try:
        joblib.dump(pipeline, model_path)
        print("Model saved successfully")
    except Exception as e:
        print(f"Error saving model: {e}")
        sys.exit(1)

    # Save metrics
    metrics_data = {
        "dataset_path": str(dataset_path),
        "model_path": str(model_path),
        "total_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "label_distribution": {
            "general_news": int((df["label"] == 0).sum()),
            "fact_check": int((df["label"] == 1).sum())
        },
        "accuracy": float(accuracy),
        "accuracy_percent": round(float(accuracy) * 100, 2),
        "classification_report": report_dict
    }

    print(f"Saving metrics to {metrics_path}...")
    try:
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, indent=2)
        print("[OK] Metrics saved successfully")
    except Exception as e:
        print(f"[ERROR] Saving metrics: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Training completed successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Start the backend: uvicorn main:app --reload")
    print("2. Open the frontend: http://127.0.0.1:5500")
    print("3. Analyze the articles")
    print()

if __name__ == "__main__":
    main()