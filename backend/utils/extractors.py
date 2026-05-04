import json
import re
from urllib.parse import urlparse
from typing import Optional, Dict

import tldextract
import trafilatura


# SSRF (Server Side Request Forgery) Protection
PRIVATE_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
PRIVATE_PREFIXES = (
    "10.", "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31."
)

def block_ssrf(url: str) -> None:
    """
    Basic SSRF protection – block private / loopback hosts or non-http(s).
    Raises ValueError if the URL is not allowed.
    """
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise ValueError("Invalid URL scheme (only http/https allowed)")

    host = (u.hostname or "").strip().lower()

    if host in PRIVATE_HOSTS:
        raise ValueError("Blocked private/loopback host")

    if any(host.startswith(p) for p in PRIVATE_PREFIXES):
        raise ValueError("Blocked private IP range")


# Blocked Domains (Non-News Sites)
BLOCKED_DOMAINS = {
    # Social Media
    "facebook.com", "fb.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "tiktok.com", "snapchat.com", "reddit.com",
    "pinterest.com", "tumblr.com", "whatsapp.com", "telegram.org",
    "discord.com", "slack.com", "wechat.com", "line.me",

    # Search Engines
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com", "baidu.com",

    # AI/Tech Services
    "openai.com", "chat.openai.com", "deepseek.com", "anthropic.com",
    "claude.ai", "gemini.google.com", "copilot.microsoft.com",
    "midjourney.com", "stability.ai",

    # Email Services
    "gmail.com", "outlook.com", "hotmail.com", "protonmail.com", "mail.com",

    # Citation Tools
    "mybib.com", "easybib.com", "citethisforme.com", "zbib.org",
    "citationmachine.net",

    # Document Tools
    "docs.google.com", "drive.google.com", "dropbox.com", "onedrive.live.com",
    "notion.so", "evernote.com", "trello.com", "asana.com",

    # Video Platforms
    "youtube.com", "youtu.be", "vimeo.com", "twitch.tv", "dailymotion.com",
    "netflix.com", "hulu.com", "disneyplus.com",

    # E-commerce
    "amazon.com", "ebay.com", "alibaba.com", "shopify.com", "etsy.com",

    # Entertainment/Gaming
    "spotify.com", "soundcloud.com", "imdb.com", "rottentomatoes.com",
    "metacritic.com", "steam.com",

    # Blogging Platforms
    "medium.com", "blogger.com", "wordpress.com", "wix.com", "squarespace.com",

    # General Tech Sites
    "github.com", "stackoverflow.com", "wikipedia.org", "quora.com",
    "canvas.com", "canvas.instructure.com",
}

BLOCKED_PATTERNS = [
    r"\.edu$",
    r"\.gov$",
]

def is_blocked_domain(domain: str) -> bool:
    if not domain:
        return False

    domain = domain.strip().lower()

    if domain in BLOCKED_DOMAINS:
        return True

    for blocked in BLOCKED_DOMAINS:
        if domain.endswith(f".{blocked}") or domain == blocked:
            return True

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, domain):
            return True

    return False


# Domain Extraction
def domain_of(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


# Article URL Heuristics + HTML Structure Validation
ARTICLE_PATH_HINTS = (
    "news", "politics", "world", "business", "economy", "markets",
    "tech", "science", "health", "sport", "sports", "opinion",
    "analysis", "investigation", "investigations", "climate", "culture"
)

def looks_like_article_url(url: str) -> bool:
    u = urlparse(url)
    path = (u.path or "").lower()

    if not path or path == "/":
        return False

    # PDFs not supported by this extractor
    if path.endswith(".pdf"):
        return False

    segs = [s for s in path.split("/") if s]
    if not segs:
        return False

    # Block common index/collection path segments
    INDEX_KEYWORDS = {"topics", "tags", "category", "categories", "search", "archive", "collections", "browse"}
    if any(keyword in segs for keyword in INDEX_KEYWORDS):
        return False

    if len(segs) >= 2:
        return True

    # URL contains a date-like pattern
    if re.search(r"\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b", path):
        return True

    # Common news section words
    if any(h in path for h in ARTICLE_PATH_HINTS):
        if len(segs) == 1 and segs[0] in ARTICLE_PATH_HINTS:
            return False
        return True

    return False


def basic_article_html_check(html: str) -> bool:
    # Quick validation: <h>, <p>:
    if not html:
        return False

    h1_ok = re.search(r"<h1[\s>]", html, flags=re.IGNORECASE) is not None
    p_count = len(re.findall(r"<p[\s>]", html, flags=re.IGNORECASE))
    article_ok = re.search(r"<article[\s>]", html, flags=re.IGNORECASE) is not None

    # block non-articles
    return h1_ok and p_count >= 3 and (article_ok or p_count >= 7)


# Article Extraction
def extract_article(url: str) -> Optional[Dict[str, str]]:
    # SSRF protection
    block_ssrf(url)

    # Reject obvious non-article pages early
    if not looks_like_article_url(url):
        raise ValueError("URL does not look like a news article page. Please paste a direct article link (not homepage).")

    # Download content
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None

    # HTML structure validation
    if not basic_article_html_check(downloaded):
        raise ValueError("This page does not appear to be a standard article (missing typical <h1>/<p>/<article> structure).")

    # Extract with metadata
    j = trafilatura.extract(
        downloaded,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        include_tables=False
    )
    if not j:
        return None

    meta = json.loads(j)

    return {
        "title": (meta.get("title") or "").strip(),
        "text": (meta.get("text") or "").strip(),
        "date": meta.get("date") or meta.get("publication_date"),
    }