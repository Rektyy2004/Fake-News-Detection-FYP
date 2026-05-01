import json
from pathlib import Path

backend_dir = Path(__file__).parent

headline_metrics_path = backend_dir / "train_model_metrics.json"
clickbait_metrics_path = backend_dir / "clickbait_model_metrics.json"


def percent(value):
    return f"{value * 100:.2f}%"


def print_headline_results():
    with open(headline_metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = data["classification_report"]

    print("HEADLINE CLASSIFICATION MODEL RESULTS")
    print("-" * 50)
    print(f"Total Samples   : {data['total_samples']}")
    print(f"Training Samples: {data['train_samples']}")
    print(f"Testing Samples : {data['test_samples']}")
    print()
    print("Label Distribution:")
    print(f"  General News  : {data['label_distribution']['general_news']}")
    print(f"  Fact-Check    : {data['label_distribution']['fact_check']}")
    print()
    print(f"Overall Accuracy: {data['accuracy_percent']:.2f}%")
    print()
    print("Class Performance:")
    print(
        f"  General News  -> "
        f"Precision: {percent(report['General News']['precision'])}, "
        f"Recall: {percent(report['General News']['recall'])}, "
        f"F1-Score: {percent(report['General News']['f1-score'])}"
    )
    print(
        f"  Fact-Check    -> "
        f"Precision: {percent(report['Fact-Check']['precision'])}, "
        f"Recall: {percent(report['Fact-Check']['recall'])}, "
        f"F1-Score: {percent(report['Fact-Check']['f1-score'])}"
    )
    print()
    print(
        f"Weighted Average F1-Score: "
        f"{percent(report['weighted avg']['f1-score'])}"
    )
    print()


def print_clickbait_results():
    with open(clickbait_metrics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("CLICKBAIT DETECTION MODEL RESULTS")
    print("-" * 50)
    print(f"Total Rows Used : {data['total_rows_used']}")
    print(f"Training Samples: {data['train_size']}")
    print(f"Testing Samples : {data['test_size']}")
    print()
    print(f"Accuracy        : {percent(data['accuracy'])}")
    print(f"F1-Score        : {percent(data['f1'])}")
    print(f"ROC-AUC         : {percent(data['roc_auc'])}")
    print()


if __name__ == "__main__":
    print_headline_results()
    print_clickbait_results()