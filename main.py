"""Disinfo Detector — FastAPI backend.
Run: uvicorn main:app --reload --port 8000
"""

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.neo4j_client import run_query, close as neo4j_close
from app.detector import run_detection
from app.pipeline import run_full_pipeline

app = FastAPI(title="Disinfo Detector", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/graph/stats")
def graph_stats():
    stats = run_query("""
        MATCH (a:Account) WITH count(a) AS accounts
        MATCH (p:Post) WITH accounts, count(p) AS posts
        MATCH (c:Claim) WITH accounts, posts, count(c) AS claims
        RETURN accounts, posts, claims
    """)
    return stats[0] if stats else {}


@app.post("/detect")
def detect():
    """Run text-based coordination detection only."""
    clusters = run_detection()
    return {
        "clusters": clusters,
        "total": len(clusters),
        "suspicious": len([c for c in clusters if c["score"] >= 30]),
    }


@app.post("/pipeline")
async def pipeline():
    """Run the full autonomous pipeline (all sponsor tools)."""
    results = await run_full_pipeline()
    return results


@app.on_event("shutdown")
def shutdown():
    neo4j_close()
