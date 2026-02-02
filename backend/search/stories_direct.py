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
    subcategory_filter: str = None,
    year_min: int = None,
    year_max: int = None,
    location_filter: str = None,
    topic_filter: str = None,
    sort_by: str = "relevance"
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
        # Reranking improves precision for hybrid/semantic/keyword but adds latency
        should_rerank = engine.enable_reranker and engine_mode in ("hybrid", "semantic", "keyword")
        
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
    
    # Apply temporal filters with scoring boost
    if year_min is not None or year_max is not None:
        filtered_results = []
        for result in enriched_results:
            keywords = result.get("keywords", "")
            # Extract years from keywords (format: "1577", "16th century", etc.)
            years = re.findall(r'\b(\d{3,4})\b', keywords)
            
            # Check if any year falls within range
            matches_filter = False
            for year_str in years:
                year = int(year_str)
                if year_min and year < year_min:
                    continue
                if year_max and year > year_max:
                    continue
                matches_filter = True
                break
            
            if matches_filter:
                # Track filter match count for sorting
                result['_filter_matches'] = result.get('_filter_matches', 0) + 1
                filtered_results.append(result)
            elif not years:
                # Include stories without explicit years
                result['_filter_matches'] = result.get('_filter_matches', 0)
                filtered_results.append(result)
        
        enriched_results = filtered_results
        logger.debug(f"Temporal filter applied: {len(enriched_results)} results remain")
    
    # Apply location filter with scoring boost
    if location_filter:
        locations = [loc.strip().lower() for loc in location_filter.split(",")]
        filtered_results = []
        for result in enriched_results:
            keywords = result.get("keywords", "").lower()
            # Check if any location appears in keywords
            if any(loc in keywords for loc in locations):
                # Track filter match count for sorting
                result['_filter_matches'] = result.get('_filter_matches', 0) + 1
                filtered_results.append(result)
        
        enriched_results = filtered_results
        logger.debug(f"Location filter applied: {len(enriched_results)} results remain")
    
    # Sort by filter match count (descending), then by score (descending)
    # This ensures stories matching more filters rank higher
    if (year_min is not None or year_max is not None or location_filter):
        enriched_results.sort(key=lambda x: (x.get('_filter_matches', 0), x['score']), reverse=True)
        # Clean up internal tracking field
        for result in enriched_results:
            result.pop('_filter_matches', None)
    
    # Apply topic filter
    if topic_filter:
        topics = [t.strip().lower() for t in topic_filter.split(",")]
        filtered_results = []
        for result in enriched_results:
            keywords = result.get("keywords", "").lower()
            # Check if any topic appears in keywords
            if any(topic in keywords for topic in topics):
                filtered_results.append(result)
        
        enriched_results = filtered_results
        logger.debug(f"Topic filter applied: {len(enriched_results)} results remain")
    
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
    
    # Apply sorting
    if sort_by and sort_by != "relevance":
        if sort_by == "chronological":
            # Sort by earliest year in keywords
            def get_earliest_year(result):
                keywords = result.get("keywords", "")
                years = re.findall(r'\b(\d{3,4})\b', keywords)
                return int(years[0]) if years else 9999  # Stories without years go last
            enriched_results.sort(key=get_earliest_year)
        
        elif sort_by == "alphabetical":
            enriched_results.sort(key=lambda x: x['title'].lower())
        
        elif sort_by == "by_book":
            enriched_results.sort(key=lambda x: (x.get('book_title', x['book_slug']), x['title']))
        
        elif sort_by == "by_pages":
            # Sort by book, then by page number
            def get_page_sort_key(result):
                book = result.get('book_title', result['book_slug'])
                pages = result.get('pages', '')
                # Extract first page number
                page_match = re.search(r'(\d+)', pages)
                page_num = int(page_match.group(1)) if page_match else 99999
                return (book, page_num)
            enriched_results.sort(key=get_page_sort_key)
    
    logger.info(f"Search returned {len(enriched_results)} story results for query: '{query}'")
    if enriched_results:
        logger.info(f"Top result: '{enriched_results[0]['title']}' | Score: {enriched_results[0]['score']:.3f}")
    
    return enriched_results
