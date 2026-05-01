# Load models and CSV/Excel files
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from .helpers import clamp01, normalize_domain, rank_to_score

try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import pytorch_cos_sim
except Exception:
    SentenceTransformer = None  # type: ignore
    pytorch_cos_sim = None  # type: ignore


def get_backend_dir() -> Path:
    """
    Returns the backend folder.
    Assumes this file is in backend/utils/analysis/loaders.py
    """
    return Path(__file__).resolve().parents[2]


def find_backend_file(*names: str) -> Optional[Path]:
    """
    Search for a file inside backend/ using one or more possible names.
    """
    backend_dir = get_backend_dir()

    for name in names:
        path = backend_dir / name
        if path.exists():
            return path

    return None


def file_mtime_iso(path: Optional[Path]) -> Optional[str]:
    """
    Return file modified time in ISO format.
    """
    if not path or not path.exists():
        return None

    try:
        return datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z"
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_sentence_model() -> Optional["SentenceTransformer"]:
    """
    Load SentenceTransformer model once.
    Returns None if the library/model is unavailable.
    """
    if SentenceTransformer is None:
        return None

    try:
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_sentence_cosine_function():
    """
    Return pytorch_cos_sim if available.
    """
    return pytorch_cos_sim


@lru_cache(maxsize=1)
def load_headline_classifier_model():
    """
    Load model.pkl from backend/.
    """
    model_path = get_backend_dir() / "model.pkl"

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found at {model_path}. Run backend/train_model.py first."
        )

    return joblib.load(model_path)


@lru_cache(maxsize=1)
def load_clickbait_model():
    """
    Load clickbait_model.pkl if it exists.
    Returns None if not found.
    """
    candidates = [
        get_backend_dir() / "clickbait_model.pkl",
        Path(__file__).resolve().parent / "clickbait_model.pkl",
    ]

    for path in candidates:
        if path.exists():
            try:
                return joblib.load(path)
            except Exception:
                return None

    return None


@lru_cache(maxsize=1)
def load_scimagomedia_index() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Load SCImago-like Excel file.

    Output:
        index[domain] = {
            "global_rank": ...,
            "overall": ...,
            ...
        }
    """
    path = find_backend_file("scimagomedia.xlsx", "SCImago Media Ranking.xlsx")

    if not path:
        return {}, {"found": False, "file": None, "updated": None}

    try:
        df = pd.read_excel(path)
    except Exception:
        return {}, {
            "found": False,
            "file": path.name,
            "updated": file_mtime_iso(path),
        }

    domain_col = None
    rank_col = None
    overall_col = None

    for column in df.columns:
        name = str(column).lower()

        if domain_col is None and "domain" in name:
            domain_col = column

        if rank_col is None and (
            "global_rank" in name or
            ("global" in name and "rank" in name) or
            name == "rank"
        ):
            rank_col = column

        if overall_col is None and ("overall" in name or "score" in name):
            overall_col = column

    if domain_col is None:
        return {}, {
            "found": False,
            "file": path.name,
            "updated": file_mtime_iso(path),
            "error": "No domain column found",
        }

    df["_base_domain"] = df[domain_col].map(normalize_domain)
    df["_rank"] = pd.to_numeric(df[rank_col], errors="coerce") if rank_col else np.nan
    df["_overall"] = pd.to_numeric(df[overall_col], errors="coerce") if overall_col else np.nan

    df = df[df["_base_domain"] != ""].copy()

    # Keep best row per domain
    df["_rank_sort"] = df["_rank"].fillna(1e18)
    df["_overall_sort"] = df["_overall"].fillna(-1e18)

    df = df.sort_values(by=["_rank_sort", "_overall_sort"], ascending=[True, False])
    df = df.drop_duplicates(subset=["_base_domain"], keep="first")

    index: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        base_domain = row["_base_domain"]

        index[base_domain] = {
            "global_rank": float(row["_rank"]) if pd.notna(row["_rank"]) else None,
            "overall": float(row["_overall"]) if pd.notna(row["_overall"]) else None,
            "country": row.get("Country", None),
            "region": row.get("Region", None),
            "language": row.get("Language", None),
            "typology": row.get("Typology", None),
        }

    meta = {
        "found": True,
        "file": path.name,
        "updated": file_mtime_iso(path),
        "unique_domains": len(index),
    }

    return index, meta


@lru_cache(maxsize=1)
def load_tranco_index() -> Tuple[Dict[str, int], Dict[str, Any]]:
    """
    Load tranco.csv

    Expected format:
    rank,domain
    """
    path = find_backend_file("tranco.csv")

    if not path:
        return {}, {"found": False, "file": None, "updated": None}

    try:
        df = pd.read_csv(path, header=None, names=["rank", "domain"], usecols=[0, 1])
    except Exception:
        return {}, {
            "found": False,
            "file": path.name,
            "updated": file_mtime_iso(path),
        }

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["base"] = df["domain"].map(normalize_domain)

    df = df[(df["base"] != "") & (df["rank"].notna())]
    df = df.sort_values("rank").drop_duplicates("base", keep="first")

    index = {str(base): int(rank) for base, rank in zip(df["base"], df["rank"])}

    meta = {
        "found": True,
        "file": path.name,
        "updated": file_mtime_iso(path),
        "unique_domains": len(index),
    }

    return index, meta


@lru_cache(maxsize=1)
def load_majestic_index() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Load majestic.csv

    Uses:
    - GlobalRank
    - Domain
    - RefSubNets
    - RefIPs
    """
    path = find_backend_file("majestic.csv")

    if not path:
        return {}, {"found": False, "file": None, "updated": None}

    try:
        df = pd.read_csv(path, usecols=["GlobalRank", "Domain", "RefSubNets", "RefIPs"])
    except Exception:
        return {}, {
            "found": False,
            "file": path.name,
            "updated": file_mtime_iso(path),
        }

    df["GlobalRank"] = pd.to_numeric(df["GlobalRank"], errors="coerce")
    df["RefSubNets"] = pd.to_numeric(df["RefSubNets"], errors="coerce")
    df["RefIPs"] = pd.to_numeric(df["RefIPs"], errors="coerce")
    df["base"] = df["Domain"].map(normalize_domain)

    df = df[(df["base"] != "") & (df["GlobalRank"].notna())]
    df = df.sort_values("GlobalRank").drop_duplicates("base", keep="first")

    index: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        index[str(row["base"])] = {
            "global_rank": int(row["GlobalRank"]),
            "ref_subnets": int(row["RefSubNets"]) if pd.notna(row["RefSubNets"]) else None,
            "ref_ips": int(row["RefIPs"]) if pd.notna(row["RefIPs"]) else None,
        }

    meta = {
        "found": True,
        "file": path.name,
        "updated": file_mtime_iso(path),
        "unique_domains": len(index),
    }

    return index, meta