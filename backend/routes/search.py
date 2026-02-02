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
            year_min=body.year_min,
            year_max=body.year_max,
            location_filter=body.location_filter,
            topic_filter=body.topic_filter,
            sort_by=body.sort_by,
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


@router.get("/topics")
def get_topics():
    """
    Get all unique topic tags extracted from story keywords.
    
    Returns:
        {"topics": ["possession", "exorcism", "ufo", ...]}
    """
    try:
        from utils.cache import get_stories_dict
        stories = get_stories_dict()
        
        # Extract all unique topics from keywords
        topics_set = set()
        for story in stories.values():
            keywords = story.get("keywords", "")
            if keywords:
                # Split by comma and clean
                topics = [t.strip().lower() for t in keywords.split(",") if t.strip()]
                topics_set.update(topics)
        
        # Sort alphabetically
        topics = sorted(list(topics_set))
        
        return {"topics": topics}
    except Exception as e:
        log.error(f"Failed to get topics: {str(e)}", exc_info=True)
        raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, "Failed to get topics", detail=str(e))


@router.post("/find-similar")
def find_similar(body: Dict[str, Any]):
    """
    Find stories similar to a given story using semantic search.
    
    Uses the story's text as a semantic query to find related stories.
    Extracts the story text using story_positions.json for accurate boundaries.
    
    Request body:
        {"title": "Story Title", "book_slug": "book_slug", "top_k": 20}
    
    Returns:
        {"results": [...]}
    """
    try:
        title = body.get("title")
        book_slug = body.get("book_slug")
        top_k = body.get("top_k", 20)
        
        if not title:
            raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, "Title is required")
        
        from storage import load_full_md, load_story_positions
        
        # Load the book's story positions
        try:
            story_positions = load_story_positions(book_slug)
        except Exception as e:
            raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, f"Failed to load story positions: {str(e)}")
        
        # Find the story's position
        story_pos = story_positions.get(title)
        if not story_pos:
            raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, f"Story position not found: '{title}'")
        
        # Load the full text and extract the story
        try:
            full_text = load_full_md(book_slug)
            start_char = story_pos.get("start_char", 0)
            end_char = story_pos.get("end_char", len(full_text))
            story_text = full_text[start_char:end_char]
        except Exception as e:
            raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, f"Failed to extract story text: {str(e)}")
        
        if not story_text or len(story_text) < 50:
            raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, f"Story text too short or empty")
            
        # Get keywords to enhance the query
        from state import app_state
        keywords = ""
        # stories_dict keys are just titles in this project
        if title in app_state.stories_dict:
            keywords = app_state.stories_dict[title].get("keywords", "")
        
        # Construct hybrid query: Title + Keywords + Text content
        # This provides a rich signal for the embedding model
        # The syntax "Title: ... Keywords: ..." helps the model distinguish parts
        prefix = f"Title: {title}. Keywords: {keywords}.\nContent: "
        
        # Calculate remaining space for text (total ~2000 chars)
        remaining_chars = 2000 - len(prefix)
        if remaining_chars < 500: # Ensure at least some text fits
            remaining_chars = 500
            
        content_chunk = story_text[:remaining_chars].strip()
        query_text = f"{prefix}{content_chunk}"
        
        # Get extra results (+10) to ensure we have enough after filtering
        results = search_stories(
            query=query_text,
            source_filter="All Sources",
            search_mode="Semantic",
            top_k=top_k + 10,
            assignment_filter="all"
        )
        
        # Filter out the source story
        filtered_results = [
            r for r in results 
            if not (r.get("title") == title and r.get("book_slug") == book_slug)
        ]
        
        return {"results": filtered_results[:top_k]}
    except AppError:
        raise
    except Exception as e:
        log.error(f"Find similar failed: {str(e)}", exc_info=True)
        raise AppError(ErrorCode.OPERATION_SEARCH_FAILED, "Find similar failed", detail=str(e))
