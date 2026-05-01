from __future__ import annotations

import math
import re
from typing import List

from . import ArticlePayload, CheckResult
from .helpers import clamp01, clamp_pct, phrase_present
from .loaders import load_clickbait_model


class clickbait_check:
    """
    Detect clickbait using:
    - rule-based signals
    - optional ML model if available
    """

    STRONG_PHRASES = [
        "shocking",
        "unbelievable",
        "secret",
        "exposed",
        "you won't believe",
        "doctors hate",
        "one weird trick",
        "what happened next",
        "blow your mind",
        "reason why",
        "never do this",
        "everyone is talking about",
        "you need to know",
    ]

    REGEX_PATTERNS = [
        r"\b\d+\s+(things|ways|reasons|tricks|secrets)\b",
        r"what happened next",
        r"this (will|could|might) change",
        r"won't believe",
        r"\btop\s+\d+\b",
        r"\bwhat you need to know\b",
    ]

    EMOTIONAL_WORDS = [
        "outrage",
        "disaster",
        "insane",
        "horrifying",
        "terrifying",
        "miracle",
        "heartbreaking",
        "stunning",
        "explosive",
    ]

    VAGUE_WORDS = ["this", "these", "thing", "something"]

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    @staticmethod
    def run(payload: ArticlePayload) -> CheckResult:
        title = (payload.title or "").strip()

        if not title:
            return CheckResult(
                name="Clickbait Detection",
                status="unknown",
                details="No headline to analyze.",
            )

        title_lower = title.lower()
        rule_score = 0
        matched_signals: List[str] = []

        for phrase in clickbait_check.STRONG_PHRASES:
            if phrase_present(title_lower, phrase):
                rule_score += 2
                matched_signals.append(f'phrase:"{phrase}"')

        for pattern in clickbait_check.REGEX_PATTERNS:
            if re.search(pattern, title_lower):
                rule_score += 2
                matched_signals.append("pattern")

        for word in clickbait_check.EMOTIONAL_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", title_lower):
                rule_score += 1
                matched_signals.append(f"emotional:{word}")

        vague_hits = [
            word for word in clickbait_check.VAGUE_WORDS
            if re.search(rf"\b{re.escape(word)}\b", title_lower)
        ]
        if vague_hits:
            rule_score += 1
            matched_signals.append(f"vague:{','.join(vague_hits[:3])}")

        exclamation_count = title.count("!")
        question_count = title.count("?")
        all_caps_words = re.findall(r"\b[A-Z]{3,}\b", title)

        if exclamation_count:
            rule_score += 1
            matched_signals.append("punct:!")

        if question_count:
            rule_score += 1
            matched_signals.append("punct:?")

        if len(all_caps_words) >= 1:
            rule_score += 1
            matched_signals.append("caps")

        # Convert rule score into probability
        rule_probability = clamp01(clickbait_check._sigmoid((rule_score - 3.0) / 1.2))

        # Optional ML model
        ml_probability = None
        model = load_clickbait_model()

        if model is not None:
            try:
                ml_probability = float(model.predict_proba([title])[0][1])
                ml_probability = clamp01(ml_probability)
            except Exception:
                ml_probability = None

        # Final probability
        if ml_probability is None:
            final_probability = rule_probability
            mode = "rule_only"
        else:
            final_probability = 0.2 * rule_probability + 0.8 * ml_probability
            mode = "hybrid"

        if final_probability >= 0.70:
            status = "fail"
        elif final_probability <= 0.30:
            status = "pass"
        else:
            status = "unknown"

        explanation = (
            " • ".join(matched_signals[:10])
            if matched_signals
            else "No strong clickbait signals detected."
        )

        return CheckResult(
            name="Clickbait Detection",
            status=status,
            details=f"Clickbait probability: {final_probability * 100:.0f}% (Mode: {mode.replace('_', ' ').title()})",
            extra={
                "mode": mode,
                "model_loaded": ml_probability is not None,
                "clickbait_probability": clamp_pct(final_probability * 100),
                "neutral_probability": clamp_pct((1.0 - final_probability) * 100),
                "rule_score": rule_score,
                "rule_probability": clamp_pct(rule_probability * 100),
                "ml_probability": clamp_pct(ml_probability * 100) if ml_probability is not None else None,
                "explanation": explanation,
            },
        )