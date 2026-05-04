from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import ArticlePayload, CheckResult
from .helpers import clamp_pct, normalize_domain, rank_to_score
from .loaders import (
    load_majestic_index,
    load_scimagomedia_index,
    load_tranco_index,
)

try:
    import whois
except Exception:
    whois = None


class domain_reputation_check:
    TRUSTED_PUBLISHERS = {
        "bbc.com": 95,
        "bbc.co.uk": 95,
        "reuters.com": 98,
        "apnews.com": 98,
        "ft.com": 92,
        "nytimes.com": 92,
        "theguardian.com": 92,
        "wsj.com": 92,
        "rte.ie": 85,
        "npr.org": 90,
        "pbs.org": 90,
        "bloomberg.com": 92,
    }

    # Sites that are known for satire or historical misinformation
    SUSPICIOUS_PUBLISHERS = {
        "theonion.com": 15,
        "babylonbee.com": 20,
        "clickhole.com": 15,
        "worldnewsdailyreport.com": 10,
        "infowars.com": 10,
        "naturalnews.com": 15,
        "newspunch.com": 15,
        "yournewswire.com": 15,
        "gatewaypundit.com": 25,
        "dailyreport.com": 20,
    }

    WEIGHT_SCIMAGO = 0.55
    WEIGHT_TRANCO = 0.25
    WEIGHT_MAJESTIC = 0.15
    WEIGHT_AGE = 0.05

    @staticmethod
    def _get_domain_age_days(domain: str) -> Optional[int]:
        if whois is None:
            return None

        try:
            data = whois.whois(domain.replace("www.", ""))
            creation_date = getattr(data, "creation_date", None)

            if isinstance(creation_date, list):
                creation_date = creation_date[0]

            if not creation_date:
                return None

            return int((datetime.now() - creation_date).days)
        except Exception:
            return None

    @staticmethod
    def _deduplicate_reasons(reasons: List[str]) -> List[str]:
        seen = set()
        output = []

        for reason in reasons:
            if reason not in seen:
                output.append(reason)
                seen.add(reason)

        return output

    @staticmethod
    def run(payload: ArticlePayload) -> CheckResult:
        raw_domain = (payload.domain or "").strip().lower()

        if not raw_domain:
            return CheckResult(
                name="Domain Reputation",
                status="unknown",
                details="No domain found.",
            )

        domain = normalize_domain(raw_domain)

        # 1a) trusted allowlist
        if domain in domain_reputation_check.TRUSTED_PUBLISHERS:
            score = float(domain_reputation_check.TRUSTED_PUBLISHERS[domain])
            return CheckResult(
                name="Domain Reputation",
                status="pass",
                details=f"Domain {domain}: trusted (score {score:.0f}/100)",
                extra={
                    "score": score,
                    "category": "trusted",
                    "source": "trusted_allowlist",
                    "reasons": ["Trusted publisher allowlist"],
                },
            )

        # 1b) suspicious list (satire/misinfo)
        if domain in domain_reputation_check.SUSPICIOUS_PUBLISHERS:
            score = float(domain_reputation_check.SUSPICIOUS_PUBLISHERS[domain])
            return CheckResult(
                name="Domain Reputation",
                status="fail",
                details=f"Domain {domain}: known satire or low-credibility source (score {score:.0f}/100)",
                extra={
                    "score": score,
                    "category": "suspicious",
                    "source": "suspicious_list",
                    "reasons": ["Known satire or historical misinformation source"],
                },
            )

        reasons: List[str] = []
        extra: Dict[str, Any] = {}

        scimagomedia_index, scimagomedia_meta = load_scimagomedia_index()
        tranco_index, tranco_meta = load_tranco_index()
        majestic_index, majestic_meta = load_majestic_index()

        extra["datasets"] = {
            "scimagomedia": scimagomedia_meta,
            "tranco": tranco_meta,
            "majestic": majestic_meta,
        }

        signals: List[Tuple[float, float, float, str]] = []
        # tuple = (weight, value, confidence, source_name)

        # 2) SCImago
        scimagomedia_data = scimagomedia_index.get(domain)
        if scimagomedia_data:
            overall_score = scimagomedia_data.get("overall")
            global_rank = scimagomedia_data.get("global_rank")

            score_value = None

            if overall_score is not None:
                score_value = max(0.0, min(1.0, float(overall_score) / 100.0))
            elif global_rank is not None:
                score_value = rank_to_score(global_rank, max_rank=50_000.0)

            if score_value is not None:
                signals.append((domain_reputation_check.WEIGHT_SCIMAGO, float(score_value), 1.0, "scimagomedia"))
                reasons.append("Listed in SCImago media rankings")

                if global_rank is not None:
                    reasons.append(f"SCImago global rank: {int(global_rank)}")

                if overall_score is not None:
                    reasons.append(f"SCImago overall score: {float(overall_score):.2f}/100")

            extra["scimagomedia_found"] = True
            extra["scimagomedia"] = scimagomedia_data
        else:
            extra["scimagomedia_found"] = False

        # 3) Tranco
        tranco_rank = tranco_index.get(domain)
        if tranco_rank is not None:
            tranco_score = rank_to_score(tranco_rank, max_rank=1_000_000.0)
            if tranco_score is not None:
                signals.append((domain_reputation_check.WEIGHT_TRANCO, float(tranco_score), 0.85, "tranco"))
                reasons.append(f"Tranco rank: {int(tranco_rank)}")
            extra["tranco_rank"] = int(tranco_rank)

        # 4) Majestic
        majestic_data = majestic_index.get(domain)
        if majestic_data:
            majestic_rank = majestic_data.get("global_rank")
            majestic_score = rank_to_score(majestic_rank, max_rank=1_000_000.0)

            if majestic_score is not None:
                signals.append((domain_reputation_check.WEIGHT_MAJESTIC, float(majestic_score), 0.80, "majestic"))
                reasons.append(f"Majestic Million rank: {int(majestic_rank)}")

            extra["majestic"] = majestic_data

        # 5) domain age
        age_days = domain_reputation_check._get_domain_age_days(domain)
        extra["age_days"] = age_days if age_days is not None else "Unknown"

        if age_days is not None:
            age_score = min(1.0, float(age_days) / 3650.0)
            signals.append((domain_reputation_check.WEIGHT_AGE, age_score, 0.60, "age"))

            if age_days < 30:
                reasons.append("Domain created within 30 days")
            elif age_days >= 3650:
                reasons.append("Domain older than 10 years")
            elif age_days >= 1095:
                reasons.append("Domain older than 3 years")

        # 6) base score
        if signals:
            numerator = sum(weight * value * confidence for weight, value, confidence, _ in signals)
            denominator = sum(weight * confidence for weight, _, confidence, _ in signals)

            base_score = 100.0 * (numerator / denominator) if denominator > 0 else 50.0
            score_source = "weighted_signals"
        else:
            base_score = 50.0
            score_source = "heuristics_only"
            reasons.append("No reputation dataset match; using heuristics only")

        final_score = clamp_pct(base_score)
        extra["source"] = score_source

        # 7) suspicious heuristics
        if domain.endswith((".xyz", ".top", ".buzz", ".gq", ".online")):
            final_score -= 15
            reasons.append("High-risk TLD")

        suspicious_keywords = ["patriot", "freedom", "truth", "uncensored", "realnews", "breakingnews"]
        if any(keyword in domain for keyword in suspicious_keywords):
            final_score -= 10
            reasons.append("Suspicious keyword in domain")

        if isinstance(age_days, int) and age_days < 30:
            final_score -= 20

        final_score = clamp_pct(final_score)

        # 8) category
        if final_score >= 80:
            category = "trusted"
        elif final_score <= 40:
            category = "suspicious"
        else:
            category = "neutral"

        # 9) status
        if final_score >= 65:
            status = "pass"
        elif final_score <= 35:
            status = "fail"
        else:
            status = "unknown"

        reasons = domain_reputation_check._deduplicate_reasons(reasons)

        return CheckResult(
            name="Domain Reputation",
            status=status,
            details=f"Domain {domain}: {category.title()} (score {final_score:.0f}/100)",
            extra={
                **extra,
                "score": final_score,
                "category": category,
                "reasons": reasons[:10],
                "signals_used": [source_name for _, _, _, source_name in signals],
            },
        )