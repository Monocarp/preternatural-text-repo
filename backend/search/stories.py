# backend/search/stories.py
"""
Story search functionality using Haystack pipelines.

Provides the main search_stories() function that supports:
- Hybrid search (semantic + keyword)
- Semantic-only search
- Keyword-only search
- Exact text match search
- Filtering by source book and assignment status
"""

import re
import logging

from state import app_state
from .pipelines import (
    document_store,
    both_pipeline,
    keyword_pipeline,
    semantic_pipeline,
)

logger = logging.getLogger(__name__)


def search_stories(
    query: str,
    source_filter: str = None,
    type_filter: str = None,
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
) -> list[dict]:
    """
    Search for stories using story-level embeddings.
    
    NOTE: This is the legacy Haystack implementation. The new parameters
    (year_min, year_max, location_filter, topic_filter, sort_by) are
    accepted but ignored. Use USE_DIRECT_SEARCH=true for full feature support.
    
    Args:
        query: Search query text
        source_filter: Book slug to filter by (or "All Sources")
        type_filter: Deprecated - story-level search is default
        search_mode: "Both" (hybrid), "Semantic", "Keywords", or "Exact"
        top_k: Maximum number of results
        min_score: Minimum relevance score threshold
        assignment_filter: "all", "assigned", or "unassigned"
    
    Returns:
        List of story result dictionaries with title, book_slug, score, etc.
    """
    logger.info(
        f"Searching for query: {query}, source: {source_filter}, "
        f"mode: {search_mode}, min_score: {min_score}"
    )
    
    # Build filters - force story-level search by default
    filters = {
        "operator": "AND",
        "conditions": [
            {"field": "type", "operator": "==", "value": "story"}
        ]
    }
    
    if source_filter and source_filter != "All Sources":
        # Convert directory name to book_slug for filtering
        filter_slug = app_state.book_dir_to_slug.get(source_filter, source_filter)
        logger.debug(f"Filtering by source: directory='{source_filter}' -> slug='{filter_slug}'")
        filters["conditions"].append({
            "field": "book",
            "operator": "==",
            "value": filter_slug
        })
    
    logger.debug(f"Applying filters: {filters}")
    filters_param = filters if filters["conditions"] else None
    
    # Run search pipeline
    try:
        if search_mode == "Both":
            results = both_pipeline.run({
                "embedder": {"text": query},
                "retriever_embedding": {"top_k": top_k, "filters": filters_param},
                "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters_param}
            })
            documents = results["joiner"]["documents"]
            
        elif search_mode == "Keywords":
            results = keyword_pipeline.run({
                "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters_param}
            })
            documents = results["retriever_bm25"]["documents"]
            
        elif search_mode == "Semantic":
            results = semantic_pipeline.run({
                "embedder": {"text": query},
                "retriever_embedding": {"top_k": top_k, "filters": filters_param}
            })
            documents = results["retriever_embedding"]["documents"]
            
        elif search_mode == "Exact":
            all_docs = document_store.filter_documents(filters=filters_param)
            documents = []
            query_text = query.strip()
            
            # Build regex pattern
            if ' ' in query_text:
                pattern = re.escape(query_text)
            else:
                pattern = r'\b' + re.escape(query_text) + r'\b'
            
            for doc in all_docs:
                count = len(re.findall(pattern, doc.content, re.IGNORECASE))
                if count > 0:
                    doc.score = count  # Use count as score
                    documents.append(doc)
        else:
            raise ValueError(f"Invalid search mode: {search_mode}")
        
        logger.debug(f"Retrieved {len(documents)} story documents")
        if documents:
            logger.info(f"Sample doc meta: {documents[0].meta}")
            logger.info(f"Sample doc score: {documents[0].score}")
            
    except Exception as e:
        logger.error(f"Search pipeline failed: {e}", exc_info=True)
        return []
    
    # Process results into story dictionaries
    stories = []
    for doc in documents:
        try:
            if doc.score <= min_score:
                continue
            
            title = doc.meta.get("title")
            book_slug = doc.meta.get("book", "unknown")
            
            if not title:
                logger.warning(f"Story document missing title: {doc.meta}")
                continue
            
            # Get book metadata (lazy import to avoid circular dependency)
            from utils.cache import get_book_metadata
            book_info = get_book_metadata(book_slug)
            
            story_result = {
                "title": title,
                "book_slug": book_slug,
                "pages": doc.meta.get("pages", "Unknown"),
                "keywords": doc.meta.get("keywords", ""),
                "start_char": doc.meta.get("start_char", 0),
                "end_char": doc.meta.get("end_char", 0),
                "score": doc.score,
                **book_info
            }
            
            # Add search_query for Exact mode (for highlighting)
            if search_mode == "Exact":
                story_result["search_query"] = query
            
            stories.append(story_result)
            
        except Exception as e:
            logger.error(f"Error processing story document: {e}", exc_info=True)
            continue
    
    # Sort by score
    sorted_results = sorted(stories, key=lambda x: x["score"], reverse=True)
    
    # Apply assignment filter
    if assignment_filter and assignment_filter != "all":
        from utils.cache import get_assigned_titles_set
        assigned_titles = get_assigned_titles_set()
        
        if assignment_filter == "assigned":
            sorted_results = [s for s in sorted_results if s['title'] in assigned_titles]
        elif assignment_filter == "unassigned":
            sorted_results = [s for s in sorted_results if s['title'] not in assigned_titles]
        
        logger.info(f"Filtered to {len(sorted_results)} {assignment_filter} stories")
    
    logger.info(f"Search returned {len(sorted_results)} story results for query: '{query}'")
    if sorted_results:
        logger.info(f"Top result: '{sorted_results[0]['title']}' | Score: {sorted_results[0]['score']:.3f}")
    
    return sorted_results
