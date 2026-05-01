from __future__ import annotations

import numpy as np

from . import ArticlePayload, CheckResult
from .loaders import load_headline_classifier_model


class headline_classifier_check:
    """
    Classify whether the article headline looks like:
    - general news
    - fact-check article

    This is informational only.
    """

    @staticmethod
    def run(payload: ArticlePayload) -> CheckResult:
        title = (payload.title or "").strip()
        text = (payload.text or "").strip()

        if not title and not text:
            return CheckResult(
                name="Headline Classification",
                status="unknown",
                details="No headline or text available.",
            )

        snippet = " ".join(text.split()[:40]) if text else ""
        model_input = f"{title} {snippet}".strip()

        try:
            model = load_headline_classifier_model()
        except Exception as error:
            return CheckResult(
                name="Headline Classification",
                status="unknown",
                details=f"Classifier unavailable: {error}",
                extra={"informational": True},
            )

        predicted_label = 0
        prob_general = None
        prob_factcheck = None

        try:
            probabilities = model.predict_proba([model_input])[0]
            prob_general = float(probabilities[0])
            prob_factcheck = float(probabilities[1])
            predicted_label = int(np.argmax(probabilities))
        except Exception:
            try:
                predicted_label = int(model.predict([model_input])[0])
            except Exception:
                predicted_label = 0

        if predicted_label == 1:
            predicted_type = "fact-check"
            details = (
                f"Headline resembles a fact-check article "
                f"(confidence: {prob_factcheck:.0%})"
                if prob_factcheck is not None
                else "Headline resembles a fact-check article"
            )
        else:
            predicted_type = "general_news"
            details = (
                f"Headline resembles general news "
                f"(confidence: {prob_general:.0%})"
                if prob_general is not None
                else "Headline resembles general news"
            )

        return CheckResult(
            name="Headline Classification",
            status="unknown",
            details=details,
            extra={
                "informational": True,
                "predicted_label": predicted_label,
                "predicted_type": predicted_type,
                "prob_general": prob_general,
                "prob_factcheck": prob_factcheck,
            },
        )