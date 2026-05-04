from __future__ import annotations
import re

from typing import Any, Dict, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from . import ArticlePayload, CheckResult
from .helpers import clamp_pct
from .loaders import get_sentence_cosine_function, get_sentence_model


class headline_body_check:
    MIN_PARAGRAPH_WORDS = 50
    TOP_K = 3
    BOTTOM_K = 3

    # Final score = 35% TF-IDF + 65% semantic
    LEXICAL_WEIGHT = 0.35
    SEMANTIC_WEIGHT = 0.65

    PASS_THRESHOLD = 0.45
    FAIL_THRESHOLD = 0.25

    BOILERPLATE_KEYWORDS = [
        "newsletter",
        "privacy policy",
        "cookies",
        "sign up",
        "subscribe",
        "advertisement",
        "sponsored",
        "terms of service",
        "all rights reserved",
        "cookie settings",
        "do not sell",
        "we value your privacy",
    ]

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))

    @staticmethod
    def _is_boilerplate(text: str) -> bool:
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in headline_body_check.BOILERPLATE_KEYWORDS)

    @staticmethod
    def _split_paragraphs(text: str) -> List[str]:
        if not text:
            return []

        clean_text = text.replace("\r\n", "\n").strip()
        raw_blocks = [block.strip() for block in re.split(r"\n\s*\n", clean_text) if block.strip()]

        paragraphs = []
        for block in raw_blocks:
            if headline_body_check._is_boilerplate(block):
                continue
            if headline_body_check._word_count(block) < headline_body_check.MIN_PARAGRAPH_WORDS:
                continue
            paragraphs.append(block)

        if len(paragraphs) < 3:
            paragraphs = []
            for block in raw_blocks:
                if headline_body_check._is_boilerplate(block):
                    continue
                if headline_body_check._word_count(block) < 30:
                    continue
                paragraphs.append(block)

        return paragraphs

    @staticmethod
    def _chunk_text_if_needed(text: str) -> List[str]:
        clean_text = re.sub(r"\s+", " ", text).strip()
        words = clean_text.split()

        chunk_size = 90
        chunks = []

        for index in range(0, len(words), chunk_size):
            chunk = " ".join(words[index:index + chunk_size]).strip()
            if chunk:
                chunks.append(chunk)

        return chunks

    @staticmethod
    def _tfidf_similarity(headline: str, paragraphs: List[str]) -> np.ndarray:
        documents = [headline] + paragraphs

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            stop_words="english",
        )

        matrix = vectorizer.fit_transform(documents)
        similarities = cosine_similarity(matrix[0:1], matrix[1:])[0]

        return np.clip(similarities, 0.0, 1.0)

    @staticmethod
    def _semantic_similarity(headline: str, paragraphs: List[str]) -> np.ndarray:
        model = get_sentence_model()
        cosine_fn = get_sentence_cosine_function()

        if model is None or cosine_fn is None:
            return np.zeros(len(paragraphs), dtype=float)

        try:
            texts = [headline] + paragraphs
            embeddings = model.encode(texts, convert_to_tensor=True)
            similarities = cosine_fn(embeddings[0], embeddings[1:]).cpu().numpy()[0]
            return np.clip(similarities, 0.0, 1.0)
        except Exception:
            return np.zeros(len(paragraphs), dtype=float)

    @staticmethod
    def _combine_scores(tfidf_scores: np.ndarray, semantic_scores: np.ndarray) -> np.ndarray:
        return (
            headline_body_check.LEXICAL_WEIGHT * np.clip(tfidf_scores, 0.0, 1.0) +
            headline_body_check.SEMANTIC_WEIGHT * np.clip(semantic_scores, 0.0, 1.0)
        )

    @staticmethod
    def _make_snippet(text: str, max_length: int = 350) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= max_length else text[:max_length].rstrip() + "…"

    @staticmethod
    def run(payload: ArticlePayload) -> CheckResult:
        title = (payload.title or "").strip()
        body = (payload.text or "").strip()

        if not title or not body:
            return CheckResult(
                name="Headline-Body Match",
                status="unknown",
                details="Missing headline or body text.",
            )

        paragraphs = headline_body_check._split_paragraphs(body)

        if len(paragraphs) < 3:
            chunked = headline_body_check._chunk_text_if_needed(body)
            if len(chunked) >= len(paragraphs):
                paragraphs = chunked

        if not paragraphs:
            return CheckResult(
                name="Headline-Body Match",
                status="unknown",
                details="No valid body sections to analyze.",
            )

        try:
            tfidf_scores = headline_body_check._tfidf_similarity(title, paragraphs)
        except Exception:
            tfidf_scores = np.zeros(len(paragraphs), dtype=float)

        semantic_scores = headline_body_check._semantic_similarity(title, paragraphs)
        combined_scores = headline_body_check._combine_scores(tfidf_scores, semantic_scores)

        sorted_indices_desc = np.argsort(combined_scores)[::-1]
        top_indices = list(sorted_indices_desc[:min(headline_body_check.TOP_K, len(sorted_indices_desc))])

        bottom_indices = []
        seen = set(top_indices)
        for index in reversed(sorted_indices_desc):
            if int(index) in seen:
                continue
            bottom_indices.append(int(index))
            if len(bottom_indices) >= headline_body_check.BOTTOM_K:
                break

        average_top_score = float(np.mean(combined_scores[top_indices])) if top_indices else 0.0

        if average_top_score >= headline_body_check.PASS_THRESHOLD:
            status = "pass"
            details = f"Headline closely matches body content (avg similarity: {average_top_score * 100:.1f}%)"
        elif average_top_score <= headline_body_check.FAIL_THRESHOLD:
            status = "fail"
            details = f"Weak headline-body match; possible mismatch (avg similarity: {average_top_score * 100:.1f}%)"
        else:
            status = "unknown"
            details = f"Mixed headline-body similarity (avg similarity: {average_top_score * 100:.1f}%)"

        evidence: List[Dict[str, Any]] = []

        for rank, index in enumerate(top_indices, start=1):
            evidence.append({
                "tier": "high",
                "rank": rank,
                "similarity": clamp_pct(combined_scores[index] * 100),
                "lexical_similarity": clamp_pct(tfidf_scores[index] * 100),
                "semantic_similarity": clamp_pct(semantic_scores[index] * 100),
                "snippet": headline_body_check._make_snippet(paragraphs[index]),
            })

        for rank, index in enumerate(bottom_indices, start=1):
            evidence.append({
                "tier": "low",
                "rank": rank,
                "similarity": clamp_pct(combined_scores[index] * 100),
                "lexical_similarity": clamp_pct(tfidf_scores[index] * 100),
                "semantic_similarity": clamp_pct(semantic_scores[index] * 100),
                "snippet": headline_body_check._make_snippet(paragraphs[index]),
            })

        return CheckResult(
            name="Headline-Body Match",
            status=status,
            details=details,
            extra={"evidence": evidence},
        )