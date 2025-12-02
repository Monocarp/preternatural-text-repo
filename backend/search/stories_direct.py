# backend/search/stories_direct.py
"""
Story search functionality using Direct FAISS + SQLite engine.

Provides the main search_stories() function that supports:
- Hybrid search (semantic + keyword via RRF)
- Semantic-only search (FAISS)
- Keyword-only search (FTS5 BM25)
- Exact text match search
- Filtering by source book and assignment status
"""

import re
import logging
from typing import List, Dict, Any, Optional

from state import app_state
from .engine import get_search_engine

logger = logging.getLogger(__name__)


# Score thresholds vary by search mode due to different scoring mechanisms
# - Semantic: cosine similarity 0-1, we want most results so use very low threshold
# - Keyword (BM25): unbounded positive, typical good match > 0
# - Hybrid (RRF): small values ~0.008-0.02, typical good match > 0.001
# Set very low thresholds to avoid filtering - let the ranking do the work
SCORE_THRESHOLDS = {
    "hybrid": 0.0001,   # RRF scores are small but meaningful
    "semantic": 0.01,   # Very low - don't filter semantic results
    "keyword": 0.0,     # BM25 scores - any positive match
    "exact": 0,         # Occurrence count - any match
}


def search_stories(
    query: str,
    source_filter: str = None,
    type_filter: str = None,  # Deprecated, always story-level
    search_mode: str = "Both",
    top_k: int = 1000,
    min_score: float = 0.2,
    assignment_filter: str = "all",
    category_filter: str = None,
    subcategory_filter: str = None
) -> List[Dict[str, Any]]:
    """
    Search for stories using Direct FAISS + SQLite engine.
    
    Args:
        query: Search query text
        source_filter: Book slug to filter by (or "All Sources")
        type_filter: Deprecated - story-level search is default
        search_mode: "Both" (hybrid), "Semantic", "Keywords", or "Exact"
        top_k: Maximum number of results
        min_score: Minimum relevance score threshold (auto-adjusted per mode)
        assignment_filter: "all", "assigned", or "unassigned"
        category_filter: Top-level category name to filter by (or None for all)
        subcategory_filter: Subcategory name to filter by (or None for all)
    
    Returns:
        List of story result dictionaries with title, book_slug, score, etc.
    """
    logger.info(
        f"Searching for query: {query}, source: {source_filter}, "
        f"mode: {search_mode}, min_score: {min_score}, "
        f"category: {category_filter}, subcategory: {subcategory_filter}"
    )
    
    # Get search engine
    engine = get_search_engine()
    
    # Map search mode to engine mode
    mode_map = {
        "Both": "hybrid",
        "Semantic": "semantic",
        "Keywords": "keyword",
        "Exact": "exact"
    }
    engine_mode = mode_map.get(search_mode, "hybrid")
    
    # Use mode-appropriate score threshold
    # Override user's min_score for hybrid mode since RRF scores are different
    effective_min_score = SCORE_THRESHOLDS.get(engine_mode, min_score)
    logger.debug(f"Using effective min_score={effective_min_score} for mode={engine_mode}")
    
    # Handle source filter
    book_filter = None
    if source_filter and source_filter != "All Sources":
        # Convert directory name to book_slug for filtering
        book_filter = app_state.book_dir_to_slug.get(source_filter, source_filter)
        logger.debug(f"Filtering by source: directory='{source_filter}' -> slug='{book_filter}'")
    
    # Run search
    try:
        # Determine if reranking should be applied
        # Reranking improves precision for hybrid/semantic but adds latency
        should_rerank = engine.enable_reranker and engine_mode in ("hybrid", "semantic")
        
        results = engine.search(
            query=query,
            mode=engine_mode,
            top_k=top_k,
            min_score=effective_min_score,
            book_filter=book_filter,
            rerank=should_rerank,
            rerank_top_k=50  # Rerank top 50 candidates for best quality
        )
        
        logger.debug(f"Retrieved {len(results)} story results (rerank={should_rerank})")
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return []
    
    # Enrich results with book metadata
    enriched_results = []
    for result in results:
        try:
            # Get book metadata (lazy import to avoid circular dependency)
            from utils.cache import get_book_metadata
            book_info = get_book_metadata(result['book_slug'])
            
            story_result = {
                "title": result['title'],
                "book_slug": result['book_slug'],
                "pages": result.get("pages", "Unknown"),
                "keywords": result.get("keywords", ""),
                "start_char": result.get("start_char", 0),
                "end_char": result.get("end_char", 0),
                "score": result['score'],
                **book_info
            }
            
            # Add search_query for Exact mode (for highlighting)
            if search_mode == "Exact":
                story_result["search_query"] = query
            
            enriched_results.append(story_result)
            
        except Exception as e:
            logger.error(f"Error enriching result: {e}", exc_info=True)
            continue
    
    # Apply assignment filter
    if assignment_filter and assignment_filter != "all":
        from utils.cache import get_assigned_titles_set
        assigned_titles = get_assigned_titles_set()
        
        if assignment_filter == "assigned":
            enriched_results = [s for s in enriched_results if s['title'] in assigned_titles]
        elif assignment_filter == "unassigned":
            enriched_results = [s for s in enriched_results if s['title'] not in assigned_titles]
        
        logger.info(f"Filtered to {len(enriched_results)} {assignment_filter} stories")
    
    # Apply category/subcategory filter
    if category_filter:
        from utils.cache import get_cached_tree
        from tree.queries import get_stories_for_subcats, _collect_stories_recursive
        
        tree = get_cached_tree()
        
        if category_filter in tree and isinstance(tree[category_filter], dict):
            category_node = tree[category_filter]
            
            if subcategory_filter:
                # Filter by specific subcategory within the category
                if subcategory_filter in category_node:
                    subcategory_titles = set()
                    subcat_value = category_node[subcategory_filter]
                    
                    if isinstance(subcat_value, list):
                        subcategory_titles.update(subcat_value)
                    elif isinstance(subcat_value, dict):
                        _collect_stories_recursive(subcat_value, subcategory_titles)
                    
                    enriched_results = [s for s in enriched_results if s['title'] in subcategory_titles]
                    logger.info(f"Filtered to {len(enriched_results)} stories in {category_filter}/{subcategory_filter}")
                else:
                    # Subcategory doesn't exist - return empty
                    enriched_results = []
                    logger.warning(f"Subcategory '{subcategory_filter}' not found in category '{category_filter}'")
            else:
                # Filter by entire category (all subcategories)
                category_titles = set()
                _collect_stories_recursive(category_node, category_titles)
                
                enriched_results = [s for s in enriched_results if s['title'] in category_titles]
                logger.info(f"Filtered to {len(enriched_results)} stories in category {category_filter}")
        else:
            # Category doesn't exist - return empty
            enriched_results = []
            logger.warning(f"Category '{category_filter}' not found in tree")
    
    logger.info(f"Search returned {len(enriched_results)} story results for query: '{query}'")
    if enriched_results:
        logger.info(f"Top result: '{enriched_results[0]['title']}' | Score: {enriched_results[0]['score']:.3f}")
    
    return enriched_results
