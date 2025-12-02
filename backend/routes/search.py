# backend/routes/search.py
"""
Search routes for the Lexicon API.

Endpoints:
- POST /api/search - Hybrid semantic + keyword story search
- GET /api/sources - List available book sources
- GET /api/categories - List available categories for filtering
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter

from .dependencies import SearchQuery
from .errors import AppError, ErrorCode
from utils import search_stories, sources
from utils.cache import get_cached_tree

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
    - category_filter: Top-level category name to filter by
    - subcategory_filter: Subcategory name to filter by (requires category_filter)
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
            category_filter=body.category_filter,
            subcategory_filter=body.subcategory_filter,
        )
        return {"results": results}
    except Exception as e:
        log.error(f"Search failed: {str(e)}", exc_info=True)
        raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, "Search failed", detail=str(e))


@router.get("/sources")
def get_sources():
    """Get list of available book sources for filtering."""
    return {"sources": sources}


@router.get("/categories")
def get_categories():
    """
    Get hierarchical list of categories for search filtering.
    
    Returns:
        {
            "categories": ["Demonic Activity", "Witchcraft", ...],
            "subcategories": {
                "Demonic Activity": ["Possession", "Obsession", ...],
                "Witchcraft": ["Curses", "Spells", ...],
                ...
            }
        }
    """
    try:
        tree = get_cached_tree()
        
        # Get top-level categories (exclude _stories key)
        categories = [key for key in tree.keys() if key != "_stories"]
        categories.sort()
        
        # Get subcategories for each top-level category
        subcategories: Dict[str, List[str]] = {}
        for category in categories:
            if isinstance(tree[category], dict):
                # Get subcategory names (exclude _stories key)
                subs = [key for key in tree[category].keys() if key != "_stories"]
                subs.sort()
                subcategories[category] = subs
            else:
                subcategories[category] = []
        
        return {
            "categories": categories,
            "subcategories": subcategories
        }
    except Exception as e:
        log.error(f"Failed to get categories: {str(e)}", exc_info=True)
        raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, "Failed to get categories", detail=str(e))
