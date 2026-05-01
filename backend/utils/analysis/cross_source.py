from __future__ import annotations

import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from dateutil import parser as dateparser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import ArticlePayload, CheckResult
from .helpers import clamp_pct, normalize_domain
from .loaders import get_sentence_cosine_function, get_sentence_model


class cross_source_check:
    @staticmethod
    def _debug_log(msg: str):
        if os.getenv("CROSS_SOURCE_DEBUG") == "1":
            print(f"[CrossSource Debug] {msg}")

    @staticmethod
    def _generate_queries(title: str) -> List[str]:
        try:
            max_queries = int(os.getenv("CROSS_SOURCE_MAX_QUERIES", "1"))
        except:
            max_queries = 1
            
        queries = [title]
        if max_queries > 1:
            words = title.split()
            if len(words) > 8:
                queries.append(" ".join(words[:8]))
        return queries[:max_queries]

    @staticmethod
    def _favicon_for(domain: str) -> str:
        if not domain:
            return ""
        return f"https://www.google.com/s2/favicons?sz=32&domain_url={domain}"

    @staticmethod
    def _fetch_from_newsapi(title: str, date: Optional[str], avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            return []

        params = {
            "q": title,
            "language": "en",
            "pageSize": "30",
            "sortBy": "relevancy",
            "apiKey": api_key,
        }

        if date:
            try:
                parsed_date = dateparser.parse(date)
                params["from"] = (parsed_date - timedelta(days=21)).strftime("%Y-%m-%d")
                params["to"] = (parsed_date + timedelta(days=21)).strftime("%Y-%m-%d")
            except Exception:
                pass

        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=12,
            )
            if response.status_code != 200:
                cross_source_check._debug_log(f"NewsAPI Error: {response.text}")
                return []

            data = response.json()
            articles = data.get("articles", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"NewsAPI Exception: {e}")
            return []

        results = []

        for article in articles:
            url = (article.get("url") or "").strip()
            if not url:
                continue

            domain = normalize_domain(url)

            if avoid_domain and domain == avoid_domain:
                continue

            results.append({
                "title": (article.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (article.get("publishedAt") or "").strip(),
                "provider": "newsapi",
            })

        return results

    @staticmethod
    def _fetch_from_serpapi(title: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            return []

        params = {
            "engine": "google_news",
            "q": title,
            "hl": "en",
            "gl": "us",
            "api_key": api_key,
        }

        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=12)
            if response.status_code != 200:
                cross_source_check._debug_log(f"SerpAPI Error: {response.text}")
                return []

            data = response.json()
            news_results = data.get("news_results", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"SerpAPI Exception: {e}")
            return []

        results = []

        for item in news_results:
            url = (item.get("link") or "").strip()
            if not url:
                continue

            domain = normalize_domain(url)

            if avoid_domain and domain == avoid_domain:
                continue

            results.append({
                "title": (item.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (item.get("date") or "").strip(),
                "provider": "serpapi",
            })

        return results

    @staticmethod
    def _fetch_from_gdelt(title: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        params = {
            "query": title,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": "50",
            "sort": "HybridRel",
        }

        try:
            response = requests.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=12,
            )
            if response.status_code != 200:
                cross_source_check._debug_log(f"GDELT Error: {response.text}")
                return []

            data = response.json()
            articles = data.get("articles", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"GDELT Exception: {e}")
            return []

        results = []

        for article in articles:
            url = (article.get("url") or "").strip()
            if not url:
                continue

            domain = normalize_domain(article.get("domain") or url)

            if avoid_domain and domain == avoid_domain:
                continue

            results.append({
                "title": (article.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (article.get("seendate") or article.get("seenDate") or "").strip(),
                "provider": "gdelt",
            })

        return results

    @staticmethod
    def _fetch_from_gnews(query: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("GNEWS_API_KEY")
        if not api_key: return []
        params = {"q": f'"{query}"', "lang": "en", "max": "10", "apikey": api_key}
        try:
            res = requests.get("https://gnews.io/api/v4/search", params=params, timeout=12)
            if res.status_code != 200:
                cross_source_check._debug_log(f"GNews Error: {res.text}")
                return []
            data = res.json()
            articles = data.get("articles", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"GNews Exception: {e}")
            return []
        
        results = []
        for article in articles:
            url = (article.get("url") or "").strip()
            if not url: continue
            domain = normalize_domain(url)
            if avoid_domain and domain == avoid_domain: continue
            results.append({
                "title": (article.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (article.get("publishedAt") or "").strip(),
                "provider": "gnews"
            })
        return results

    @staticmethod
    def _fetch_from_currents(query: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("CURRENTS_API_KEY")
        if not api_key: return []
        params = {"keywords": query, "language": "en", "apiKey": api_key}
        try:
            res = requests.get("https://api.currentsapi.services/v1/search", params=params, timeout=12)
            if res.status_code != 200:
                cross_source_check._debug_log(f"Currents Error: {res.text}")
                return []
            data = res.json()
            news = data.get("news", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"Currents Exception: {e}")
            return []
        
        results = []
        for item in news:
            url = (item.get("url") or "").strip()
            if not url: continue
            domain = normalize_domain(url)
            if avoid_domain and domain == avoid_domain: continue
            results.append({
                "title": (item.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (item.get("published") or "").strip(),
                "provider": "currents"
            })
        return results

    @staticmethod
    def _fetch_from_guardian(query: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("GUARDIAN_API_KEY")
        if not api_key: return []
        params = {"q": query, "api-key": api_key}
        try:
            res = requests.get("https://content.guardianapis.com/search", params=params, timeout=12)
            if res.status_code != 200:
                cross_source_check._debug_log(f"Guardian Error: {res.text}")
                return []
            data = res.json()
            results_data = data.get("response", {}).get("results", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"Guardian Exception: {e}")
            return []
            
        results = []
        for item in results_data:
            url = (item.get("webUrl") or "").strip()
            if not url: continue
            domain = normalize_domain(url)
            if avoid_domain and domain == avoid_domain: continue
            results.append({
                "title": (item.get("webTitle") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (item.get("webPublicationDate") or "").strip(),
                "provider": "guardian"
            })
        return results

    @staticmethod
    def _fetch_from_mediastack(query: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("MEDIASTACK_API_KEY")
        if not api_key: return []
        params = {"access_key": api_key, "keywords": query, "languages": "en"}
        try:
            res = requests.get("http://api.mediastack.com/v1/news", params=params, timeout=12)
            if res.status_code != 200:
                cross_source_check._debug_log(f"Mediastack Error: {res.text}")
                return []
            data = res.json()
            articles = data.get("data", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"Mediastack Exception: {e}")
            return []
            
        results = []
        for item in articles:
            url = (item.get("url") or "").strip()
            if not url: continue
            domain = normalize_domain(url)
            if avoid_domain and domain == avoid_domain: continue
            results.append({
                "title": (item.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (item.get("published_at") or "").strip(),
                "provider": "mediastack"
            })
        return results

    @staticmethod
    def _fetch_from_google_factcheck(query: str, avoid_domain: Optional[str]) -> List[Dict[str, Any]]:
        api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY")
        if not api_key: return []
        params = {"query": query, "key": api_key}
        try:
            res = requests.get("https://factchecktools.googleapis.com/v1alpha1/claims:search", params=params, timeout=12)
            if res.status_code != 200:
                cross_source_check._debug_log(f"FactCheck Error: {res.text}")
                return []
            data = res.json()
            claims = data.get("claims", []) or []
        except Exception as e:
            cross_source_check._debug_log(f"FactCheck Exception: {e}")
            return []
            
        results = []
        for claim in claims:
            claim_reviews = claim.get("claimReview", [])
            if not claim_reviews: continue
            review = claim_reviews[0]
            url = (review.get("url") or "").strip()
            if not url: continue
            domain = normalize_domain(url)
            if avoid_domain and domain == avoid_domain: continue
            results.append({
                "title": (review.get("title") or claim.get("text") or "").strip(),
                "url": url,
                "domain": domain,
                "publishedAt": (review.get("reviewDate") or "").strip(),
                "provider": "google_factcheck"
            })
        return results

    @staticmethod
    def _tfidf_title_similarity(query_title: str, titles: List[str]) -> np.ndarray:
        documents = [query_title] + titles

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
    def run(payload: ArticlePayload) -> CheckResult:
        title = (payload.title or "").strip()

        if not title:
            return CheckResult(
                name="Cross-Source Verification",
                status="unknown",
                details="No title for cross-source check.",
            )

        avoid_domain = normalize_domain(payload.domain or "")
        
        queries = cross_source_check._generate_queries(title)
        candidates: List[Dict[str, Any]] = []

        for q in queries:
            cross_source_check._debug_log(f"Querying for: {q}")
            candidates += cross_source_check._fetch_from_newsapi(q, payload.date, avoid_domain)
            candidates += cross_source_check._fetch_from_serpapi(q, avoid_domain)
            candidates += cross_source_check._fetch_from_gdelt(q, avoid_domain)
            candidates += cross_source_check._fetch_from_gnews(q, avoid_domain)
            candidates += cross_source_check._fetch_from_currents(q, avoid_domain)
            candidates += cross_source_check._fetch_from_guardian(q, avoid_domain)
            candidates += cross_source_check._fetch_from_mediastack(q, avoid_domain)
            candidates += cross_source_check._fetch_from_google_factcheck(q, avoid_domain)

        candidates = [item for item in candidates if (item.get("title") or "").strip()]

        if not candidates:
            return CheckResult(
                name="Cross-Source Verification",
                status="unknown",
                details="No similar coverage found (APIs unavailable or no matches).",
            )

        # Remove duplicate URLs
        seen_urls = set()
        unique_candidates = []

        for item in candidates:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique_candidates.append(item)

        candidates = unique_candidates

        other_titles = [item["title"] for item in candidates]

        model = get_sentence_model()
        cosine_fn = get_sentence_cosine_function()

        if model is not None and cosine_fn is not None:
            try:
                embeddings = model.encode([title] + other_titles, convert_to_tensor=True)
                similarities = cosine_fn(embeddings[0], embeddings[1:]).cpu().numpy()[0]
                similarities = np.clip(similarities, 0.0, 1.0)
                similarity_mode = "semantic"
            except Exception as e:
                cross_source_check._debug_log(f"SentenceModel Exception: {e}")
                similarities = cross_source_check._tfidf_title_similarity(title, other_titles)
                similarity_mode = "tfidf_fallback"
        else:
            similarities = cross_source_check._tfidf_title_similarity(title, other_titles)
            similarity_mode = "tfidf_only"

        similar_sources: List[Dict[str, Any]] = []

        for candidate, similarity in zip(candidates, similarities):
            similarity = float(similarity)

            if similarity < 0.35:
                continue

            domain = candidate.get("domain") or ""

            similar_sources.append({
                "title": candidate.get("title") or "",
                "domain": domain,
                "url": candidate.get("url") or "",
                "publishedAt": candidate.get("publishedAt") or "",
                "favicon": cross_source_check._favicon_for(domain),
                "similarity": clamp_pct(similarity * 100),
                "provider": candidate.get("provider") or "",
            })

        similar_sources.sort(key=lambda item: float(item.get("similarity", 0.0)), reverse=True)

        if not similar_sources:
            return CheckResult(
                name="Cross-Source Verification",
                status="unknown",
                details="No strong headline matches after filtering.",
                extra={"similarity_mode": similarity_mode},
            )

        best_similarity = float(similar_sources[0].get("similarity", 0.0))
        count = len(similar_sources)

        if count >= 6 and best_similarity >= 55:
            confidence = "strong"
            status = "pass"
        elif count >= 3 and best_similarity >= 45:
            confidence = "moderate"
            status = "pass"
        else:
            confidence = "weak"
            status = "unknown"

        return CheckResult(
            name="Cross-Source Verification",
            status=status,
            details=f"Found {count} similar headlines • Confirmation: {confidence.title()} • Mode: {similarity_mode.replace('_', ' ').title()}",
            extra={
                "confidence": confidence,
                "similarity_mode": similarity_mode,
                "sources": similar_sources[:10],
            },
        )
