from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse

# For domains like bbc.co.uk or elpais.com.uy
COMMON_SECOND_LEVEL_DOMAINS = {"co", "com", "org", "net", "gov", "edu"}

def clamp01(value: Any) -> float:

    try:
        number = float(value)
    except Exception:
        return 0.0

    return max(0.0, min(1.0, number))

def clamp_pct(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        return 0.0

    return max(0.0, min(100.0, number))


def phrase_present(text_lower: str, phrase_lower: str) -> bool:
    if not text_lower or not phrase_lower:
        return False

    if " " in phrase_lower:
        return phrase_lower in text_lower

    pattern = rf"\b{re.escape(phrase_lower)}\b"
    return re.search(pattern, text_lower) is not None


def normalize_domain(raw: Any) -> str:
    # Convert URL/domain-like input into a clean base domain.
    if raw is None:
        return ""

    text = str(raw).strip().lower()
    if not text:
        return ""

    text = text.replace("\\", "/")

    host = text

    # If it looks like a full URL, extract hostname
    if "://" in text:
        try:
            parsed = urlparse(text)
            host = (parsed.hostname or "").strip().lower()
        except Exception:
            host = text

    # Remove path
    host = host.split("/")[0].strip().lower()
    host = host.split(":")[0].strip().lower()
    host = host.strip(".")

    if host.startswith("www."):
        host = host[4:]

    parts = [part for part in host.split(".") if part]

    if len(parts) <= 2:
        return ".".join(parts)

    tld = parts[-1]
    second_level = parts[-2]

    if len(tld) == 2 and second_level in COMMON_SECOND_LEVEL_DOMAINS and len(parts) >= 3:
        return f"{parts[-3]}.{second_level}.{tld}"

    return f"{parts[-2]}.{parts[-1]}"


def rank_to_score(rank: Any, max_rank: float = 1_000_000.0) -> float | None:
    """
    Convert a rank into a score between 0 and 1.
    Better rank -> higher score.

    rank 1 => close to 1.0
    large rank => closer to 0.0
    """
    try:
        rank_number = float(rank)
    except Exception:
        return None

    if rank_number <= 1:
        return 1.0

    rank_number = max(1.0, min(max_rank, rank_number))

    try:
        score = 1.0 - (math.log(rank_number) / math.log(max_rank))
        return clamp01(score)
    except Exception:
        return None