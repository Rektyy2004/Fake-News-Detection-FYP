from __future__ import annotations

import time

from dateutil import parser as dateparser

from . import ArticlePayload, CheckResult


class recency_check:
    HIGH_SENSITIVITY_KEYWORDS = [
        "breaking",
        "live",
        "today",
        "yesterday",
        "election",
        "attack",
        "shooting",
        "earthquake",
        "storm",
        "hurricane",
        "ceasefire",
        "market",
        "stocks",
        "inflation",
    ]

    LOW_SENSITIVITY_KEYWORDS = [
        "history",
        "ranking",
        "rankings",
        "research",
        "study",
        "analysis",
        "opinion",
        "timeline",
        "biography",
    ]

    @staticmethod
    def run(payload: ArticlePayload) -> CheckResult:
        if not payload.date:
            return CheckResult(
                name="Recency Check",
                status="unknown",
                details="No publication date found.",
            )

        try:
            published_datetime = dateparser.parse(payload.date)
            if not published_datetime:
                raise ValueError("Could not parse publication date")

            days_since = (time.time() - published_datetime.timestamp()) / 86400.0
            days_since_int = int(max(0, days_since))
            published_date_str = published_datetime.strftime("%Y-%m-%d")

            full_text = f"{payload.title or ''} {payload.text or ''}".lower()

            sensitivity = "medium"
            if any(keyword in full_text for keyword in recency_check.HIGH_SENSITIVITY_KEYWORDS):
                sensitivity = "high"
            elif any(keyword in full_text for keyword in recency_check.LOW_SENSITIVITY_KEYWORDS):
                sensitivity = "low"

            if days_since_int <= 7:
                age_bucket = "fresh"
            elif days_since_int <= 30:
                age_bucket = "recent"
            elif days_since_int <= 180:
                age_bucket = "moderately old"
            else:
                age_bucket = "outdated"

            if sensitivity == "high":
                if days_since_int <= 30:
                    status = "pass"
                elif days_since_int > 90:
                    status = "fail"
                else:
                    status = "unknown"
            elif sensitivity == "low":
                if days_since_int <= 365:
                    status = "pass"
                else:
                    status = "unknown"
            else:
                if days_since_int <= 180:
                    status = "pass"
                else:
                    status = "unknown"

            return CheckResult(
                name="Recency Check",
                status=status,
                details=(
                    f"{age_bucket.title()} ({days_since_int} days old, "
                    f"published {published_date_str}) • Sensitivity: {sensitivity.title()}"
                ),
                extra={
                    "published_date": published_date_str,
                    "days_since": days_since_int,
                    "age_bucket": age_bucket,
                    "topic_sensitivity": sensitivity,
                },
            )

        except Exception:
            return CheckResult(
                name="Recency Check",
                status="unknown",
                details=f"Could not parse date: {payload.date}",
            )