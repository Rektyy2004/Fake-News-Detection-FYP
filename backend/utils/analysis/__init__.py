from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import numpy as np
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Type Definitions
Status = Literal["pass", "fail", "unknown"]


@dataclass
class ArticlePayload:
    """Input data for credibility analysis."""
    title: str
    text: str
    date: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None


@dataclass
class CheckResult:
    """Result returned by one credibility check."""
    name: str
    status: Status
    details: str
    extra: Dict[str, Any] = field(default_factory=dict)


# Import all split check modules
from .headline_classifier import headline_classifier_check
from .headline_body import headline_body_check
from .domain_reputation import domain_reputation_check
from .clickbait import clickbait_check
from .recency import recency_check
from .cross_source import cross_source_check


# List of all checks
ALL_CHECKS = [
    ("Headline-Body Match", headline_body_check),
    ("Domain Reputation", domain_reputation_check),
    ("Clickbait Detection", clickbait_check),
    ("Recency Check", recency_check),
    ("Cross-Source Verification", cross_source_check),
    ("Headline Classification", headline_classifier_check),
]

# Helpers
def _safe_run_check(name: str, check_class, payload: ArticlePayload) -> CheckResult:
    """
    Run one check safely.
    If the check crashes, return an 'unknown' result instead of stopping everything.
    """
    try:
        result = check_class.run(payload)

        if not isinstance(result, CheckResult):
            raise ValueError("Invalid check result type")

        if not isinstance(result.extra, dict):
            result.extra = {}

        return result

    except Exception as error:
        return CheckResult(
            name=name,
            status="unknown",
            details=f"Check failed: {error}",
            extra={},
        )


def _status_to_score(status: str) -> float:
    """
    Convert check status into numeric score.

    pass    -> 1.0
    unknown -> 0.5
    fail    -> 0.0
    """
    if status == "pass":
        return 1.0
    if status == "unknown":
        return 0.5
    return 0.0

# Main Orchestration Function
def analyze_credibility(
    title: str,
    text: str,
    date: Optional[str] = None,
    domain: Optional[str] = None,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run all credibility checks and return one JSON-ready result.

    Returns:
    {
        "overall_score": float,
        "checks": [
            {
                "name": ...,
                "status": ...,
                "details": ...,
                ...
            }
        ]
    }
    """

    payload = ArticlePayload(
        title=title or "",
        text=text or "",
        date=date,
        domain=domain,
        url=url,
    )

    check_results: List[CheckResult] = []

    for check_name, check_class in ALL_CHECKS:
        result = _safe_run_check(check_name, check_class, payload)
        check_results.append(result)

    # Calculate overall score
    if check_results:
        overall_score = float(np.mean([_status_to_score(result.status) for result in check_results]))
    else:
        overall_score = 0.0

    # Convert results to JSON-safe dictionaries
    checks_json: List[Dict[str, Any]] = []

    for result in check_results:
        entry = {
            "name": result.name,
            "status": result.status,
            "details": result.details,
        }

        # Merge extra data into output
        entry.update(result.extra)
        checks_json.append(entry)

    return {
        "overall_score": overall_score,
        "checks": checks_json,
    }