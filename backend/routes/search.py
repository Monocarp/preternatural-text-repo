# backend/routes/search.py
"""
Search routes for the Lexicon API.

Endpoints:
- POST /api/search - Hybrid semantic + keyword story search
- GET /api/sources - List available book sources
"""

import logging
from fastapi import APIRouter, HTTPException

from .dependencies import SearchQuery
from utils import search_stories, sources

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
def api_search(body: SearchQuery):
    """
    Search stories using hybrid semantic + keyword search.
    
    Supports filtering by:
    - source_filter: Book source name or "All Sources"
    - type_filter: "Both", "Story", or "Non-Story"
    - search_mode: "Both" (hybrid), "Keywords", "Semantic", or "Exact"
    - assignment_filter: "all", "assigned", or "unassigned"
    - min_score: Minimum relevance threshold (0.0-1.0)
    
    Returns list of matching stories with scores.
    """
    try:
        results = search_stories(
            query=body.query,
            source_filter=body.source_filter,
            type_filter=body.type_filter,
            search_mode=body.search_mode,
            top_k=body.top_k,
            min_score=body.min_score,
            assignment_filter=body.assignment_filter,
        )
        return {"results": results}
    except Exception as e:
        log.error(f"Search failed: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Search failed: {str(e)}")


@router.get("/sources")
def get_sources():
    """Get list of available book sources for filtering."""
    return {"sources": sources}
