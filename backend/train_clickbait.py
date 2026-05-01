from pathlib import Path
import json
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score, f1_score, roc_auc_score


BASE_DIR = Path(__file__).resolve().parent
DATASET1 = BASE_DIR / "clickbait_dataset1.csv"
DATASET2 = BASE_DIR / "clickbait_dataset2.csv"
MODEL_PATH = BASE_DIR / "clickbait_model.pkl"
CLEANED_DATA_PATH = BASE_DIR / "clickbait_training_cleaned.csv"
METRICS_PATH = BASE_DIR / "clickbait_model_metrics.json"


def load_and_merge_datasets() -> pd.DataFrame:
    # Dataset 1: columns = headline, clickbait
    df1 = pd.read_csv(DATASET1)
    df1 = df1.rename(columns={"headline": "headline", "clickbait": "label"})
    df1 = df1[["headline", "label"]].copy()

    # Dataset 2: columns = label, title
    df2 = pd.read_csv(DATASET2)
    df2 = df2.rename(columns={"title": "headline"})
    df2["label"] = df2["label"].map({"clickbait": 1, "news": 0})
    df2 = df2[["headline", "label"]].copy()

    df = pd.concat([df1, df2], ignore_index=True)

    # Clean text
    df["headline"] = (
        df["headline"]
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # Drop empty / null rows
    df = df.dropna(subset=["headline", "label"])
    df = df[df["headline"] != ""]
    df["label"] = df["label"].astype(int)

    # Remove exact duplicate rows
    df = df.drop_duplicates(subset=["headline", "label"]).copy()

    # Remove conflicting duplicates & same headline appears once as clickbait and once as non-clickbait
    label_counts = df.groupby("headline")["label"].nunique()
    conflicting_headlines = label_counts[label_counts > 1].index
    df = df[~df["headline"].isin(conflicting_headlines)].copy()

    df = df.reset_index(drop=True)
    return df


def build_model() -> Pipeline:
    return Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=True,
                strip_accents="unicode",
                ngram_range=(1, 3),
                min_df=2, #repeated word more than 2 times
                max_df=0.95, #less than 95% of the documents
                sublinear_tf=True,
                stop_words="english",
            ),
        ),
        (
            "clf",
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                solver="liblinear",
                C=2.0,
                random_state=42, #same result
            ),
        ),
    ])


def main() -> None:
    if not DATASET1.exists():
        raise FileNotFoundError(f"Missing file: {DATASET1}")
    if not DATASET2.exists():
        raise FileNotFoundError(f"Missing file: {DATASET2}")

    df = load_and_merge_datasets()
    df.to_csv(CLEANED_DATA_PATH, index=False)

    X = df["headline"]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2, #80% training, 20% testing
        random_state=42,
        stratify=y,
    )

    model = build_model()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "total_rows_used": int(len(df)),
    }

    print("\n=== Evaluation ===")
    print(json.dumps(metrics, indent=2))
    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred, digits=4))

    joblib.dump(model, MODEL_PATH)

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nSaved model to: {MODEL_PATH}")
    print(f"Saved cleaned dataset to: {CLEANED_DATA_PATH}")
    print(f"Saved metrics to: {METRICS_PATH}")


if __name__ == "__main__":
    main()