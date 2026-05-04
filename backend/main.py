import numbers
import uuid
import numpy as np
from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from utils.extractors import extract_article, domain_of, is_blocked_domain
from utils.analysis import analyze_credibility

class AnalysisRecord(BaseModel):
    id: str
    url: str
    domain: str
    title: str
    timestamp: str
    overall_label: str
    overall_score: float
    checks: List[Dict]


url_history: List[AnalysisRecord] = []
MAX_HISTORY_SIZE = 100

def to_jsonable(x):
    if isinstance(x, dict):
        return {k: to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, (np.generic,)):
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            return float(x)
        if isinstance(x, np.bool_):
            return bool(x)
        return x.item()
    if isinstance(x, numbers.Number):
        return x
    if hasattr(x, "tolist"):
        try:
            return x.tolist()
        except Exception:
            return str(x)
    return x


app = FastAPI(
    title="Fake News Checkmate API",
    description="Backend to analyze news article credibility with history tracking.",
    version="2.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


def label_from_score(score01: float) -> str:
    pct = max(0.0, min(100.0, float(score01) * 100.0))
    if pct >= 80:
        return "Likely Real"
    if pct >= 60:
        return "Probably Real"
    if pct >= 40:
        return "Mixed / Uncertain"
    if pct >= 20:
        return "Probably Fake"
    return "Likely Fake"


@app.get("/analyze")
async def analyze(url: str):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    domain = domain_of(url)
    if is_blocked_domain(domain):
        raise HTTPException(
            status_code=403,
            detail=f"Blocked domain: {domain}. Please enter a valid news/article webpage."
        )

    try:
        art = extract_article(url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not art:
        raise HTTPException(status_code=400, detail="Could not extract article content. Try another article link.")

    title = art.get("title") or ""
    text = art.get("text") or ""
    date = art.get("date")

    paragraphs = [p for p in text.split('\n') if len(p.strip()) > 30]
    word_count = len(text.split())

    if word_count < 100 or len(paragraphs) < 2:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Insufficient article text extracted ({word_count} words, {len(paragraphs)} paragraphs). "
                "The analysis requires at least ~100 words and 2 paragraphs to be reliable. "
                "Please try a different article page."
            )
        )

    cred = analyze_credibility(title, text, date, domain)
    overall_score = float(cred.get("overall_score", 0.0))
    overall_label = label_from_score(overall_score)

    record_id = uuid.uuid4().hex
    record = AnalysisRecord(
        id=record_id,
        url=url,
        domain=domain,
        title=title,
        timestamp=datetime.utcnow().isoformat(),
        overall_label=overall_label,
        overall_score=overall_score,
        checks=to_jsonable(cred.get("checks", []))
    )

    url_history.insert(0, record)
    if len(url_history) > MAX_HISTORY_SIZE:
        url_history.pop()

    response = {
        "history_id": record_id,
        "title": title,
        "overall_label": overall_label,
        "overall_score": overall_score,
        "checks": cred.get("checks", []),
    }

    return JSONResponse(content=to_jsonable(response))

@app.get("/history")
async def get_history(limit: int = 20):
    limit = min(limit, MAX_HISTORY_SIZE)
    return JSONResponse(
        content={
            "total": len(url_history),
            "limit": limit,
            "records": [rec.dict() for rec in url_history[:limit]]
        }
    )

@app.get("/history/{record_id}")
async def get_history_item(record_id: str):
    for record in url_history:
        if record.id == record_id:
            return JSONResponse(content=record.dict())
    raise HTTPException(status_code=404, detail="History record not found")

@app.delete("/history")
async def clear_history():
    url_history.clear()
    return {"message": "History cleared successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)