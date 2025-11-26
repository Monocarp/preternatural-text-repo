# backend/search/__init__.py
"""
Search module - Story search with FAISS + SQLite (Direct) or Haystack (Legacy).

This module handles all search operations including:
- Pipeline/engine initialization
- Document store management
- Story search with filtering

Set USE_DIRECT_SEARCH=true to use the new Direct FAISS + SQLite engine.
Set USE_DIRECT_SEARCH=false to use legacy Haystack pipelines.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Feature flag: Use Direct FAISS + SQLite instead of Haystack
# Default to False for safe rollout, set to True after migration
USE_DIRECT_SEARCH = os.environ.get("USE_DIRECT_SEARCH", "false").lower() == "true"

if USE_DIRECT_SEARCH:
    logger.info("Using Direct FAISS + SQLite search engine")
    
    # Import from new direct engine
    from .engine_compat import (
        initialize_search_engine,
        get_document_store,
        get_both_pipeline,
        get_keyword_pipeline,
        get_semantic_pipeline,
        get_embedder_doc,
        get_model_path,
    )
    
    # Initialize on import
    initialize_search_engine()
    
    # Provide module-level variables for backward compatibility
    document_store = get_document_store()
    both_pipeline = get_both_pipeline()
    keyword_pipeline = get_keyword_pipeline()
    semantic_pipeline = get_semantic_pipeline()
    embedder_doc = get_embedder_doc()
    MODEL_PATH = get_model_path()
    
    # Use direct search function
    from .stories_direct import search_stories
    
else:
    logger.info("Using legacy Haystack search pipelines")
    
    # Import from legacy Haystack pipelines
    from .pipelines import (
        document_store,
        both_pipeline,
        keyword_pipeline,
        semantic_pipeline,
        embedder_doc,
        MODEL_PATH,
    )
    from .stories import search_stories


__all__ = [
    # Pipelines/Engine
    "document_store",
    "both_pipeline",
    "keyword_pipeline",
    "semantic_pipeline",
    "embedder_doc",
    "MODEL_PATH",
    # Functions
    "search_stories",
    # Feature flag
    "USE_DIRECT_SEARCH",
]
