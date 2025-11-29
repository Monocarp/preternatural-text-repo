# backend/utils_legacy.py
"""
Legacy compatibility shim.

This module re-exports functions from the new modular structure for backwards compatibility.
New code should import directly from the specific modules:

    # Instead of:
    from utils_legacy import search_stories, load_full_md
    
    # Use:
    from search import search_stories
    from storage import load_full_md
    from tree import load_codex_tree
    from sync import sync_disk_to_db

This shim ensures existing code continues to work during the transition.
"""

import logging

# Import centralized state
from state import app_state

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Backwards Compatibility: State Aliases
# ------------------------------------------------------------------ #
# These allow `from utils_legacy import stories_dict` to still work

# Paths
books_dir = app_state.books_dir
data_dir = app_state.data_dir
document_store_path = app_state.document_store_path
codex_tree_path = app_state.codex_tree_path
stories_dict_path = app_state.stories_dict_path
pending_stories_path = app_state.pending_stories_path

# Database
USE_DB = app_state.USE_DB
engine = app_state.engine
SessionLocal = app_state.SessionLocal

# Caches - reference from state
stories_dict = app_state.stories_dict
_book_metadata_cache = app_state.book_metadata_cache
full_mds = app_state.full_mds
story_positions = app_state.story_positions

# Book discovery
books = app_state.books
sources = app_state.sources
book_dir_to_slug = app_state.book_dir_to_slug

# ------------------------------------------------------------------ #
# Re-exports from search module
# ------------------------------------------------------------------ #
from search import (
    document_store,
    both_pipeline,
    keyword_pipeline,
    semantic_pipeline,
    embedder_doc,
    MODEL_PATH,
    search_stories,
)

# ------------------------------------------------------------------ #
# Re-exports from storage module
# ------------------------------------------------------------------ #
from storage import (
    load_full_md,
    load_story_positions,
    save_story_positions,
    update_story_boundaries,
    update_story_title,
    update_story_keywords,
    load_pending_stories,
    save_pending_stories,
    check_story_overlap,
)

# ------------------------------------------------------------------ #
# Re-exports from tree module
# ------------------------------------------------------------------ #
from tree import (
    CATEGORIES,
    merge_trees,
    find_paths_for_title,
    load_codex_tree,
    save_codex_tree,
    load_codex_tree_from_json,
    save_codex_tree_to_json,
)

# Wrapper for assign_to_path that provides stories_dict
from tree.operations import assign_to_path as _assign_to_path

def assign_to_path(tree, path, story):
    """Assign story to path in tree - wrapper that provides stories_dict"""
    return _assign_to_path(tree, path, story, app_state.stories_dict)

# ------------------------------------------------------------------ #
# Re-exports from sync module
# ------------------------------------------------------------------ #
from sync import (
    sync_disk_to_db,
    sync_books_from_metadata,
    load_all_stories,
    enrich_stories_with_book_metadata,
    get_stories_at_path,
)

# ------------------------------------------------------------------ #
# Re-exports from utils/cache module
# ------------------------------------------------------------------ #
from utils.cache import invalidate_cache

# ------------------------------------------------------------------ #
# Legacy aliases for database connection check
# ------------------------------------------------------------------ #
# Some old code may check these directly
def _update_db_state():
    """Update module-level DB state from app_state (for backwards compat)"""
    global USE_DB, SessionLocal, engine
    USE_DB = app_state.USE_DB
    SessionLocal = app_state.SessionLocal
    engine = app_state.engine

_update_db_state()

logger.info("utils_legacy shim loaded - re-exporting from modular structure")
