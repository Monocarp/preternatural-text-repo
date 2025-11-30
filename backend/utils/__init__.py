# backend/utils/__init__.py
"""
Utils package - re-exports for backward compatibility and convenience.

This module aggregates exports from:
- utils_legacy.py (state, search, sync)
- utils/rendering.py
- utils/cache.py
- utils/storage.py
- utils/export.py
- utils/tree_ops.py
"""

from utils_legacy import *
from .rendering import render_md_with_scroll_and_highlight, render_static_story, find_book_slug
from .cache import invalidate_cache, get_cached_tree, get_book_metadata, clear_book_metadata_cache, preload_book_metadata, get_assigned_titles_set, rebuild_assigned_titles_cache, clear_assigned_titles_cache
from .storage import load_full_md, load_story_positions, save_story_positions, update_story_boundaries, update_story_title, update_story_keywords, load_pending_stories, save_pending_stories, check_story_overlap
from .export import export_stories, export_updated_jsons
from .tree_ops import CATEGORIES, merge_trees, remove_from_path, find_paths_for_title

# Import assign_to_path from utils_legacy which provides the stories_dict automatically
from utils_legacy import assign_to_path

# Re-export additional items from utils_legacy that routes need
from utils_legacy import (
    # State
    stories_dict,
    stories_dict_path,
    story_positions,
    USE_DB,
    SessionLocal,
    engine,
    sources,
    # Search
    document_store,
    both_pipeline,
    search_stories,
    # Tree
    load_codex_tree,
    save_codex_tree,
    save_codex_tree_to_json,
    # Sync
    sync_disk_to_db,
    enrich_stories_with_book_metadata,
    get_stories_at_path,
)

__all__ = [
    # rendering
    "render_md_with_scroll_and_highlight", 
    "render_static_story", 
    "find_book_slug",
    # cache
    "invalidate_cache",
    "get_cached_tree",
    "get_book_metadata",
    "clear_book_metadata_cache",
    "preload_book_metadata",
    "get_assigned_titles_set",
    "rebuild_assigned_titles_cache",
    "clear_assigned_titles_cache",
    # storage
    "load_full_md",
    "load_story_positions",
    "save_story_positions",
    "update_story_boundaries",
    "update_story_title",
    "update_story_keywords",
    "load_pending_stories",
    "save_pending_stories",
    "check_story_overlap",
    # export
    "export_stories",
    "export_updated_jsons",
    # tree_ops
    "CATEGORIES",
    "merge_trees",
    "assign_to_path",
    "remove_from_path",
    "find_paths_for_title",
    # state
    "stories_dict",
    "stories_dict_path",
    "story_positions",
    "USE_DB",
    "SessionLocal",
    "engine",
    "sources",
    # search
    "document_store",
    "both_pipeline",
    "search_stories",
    # tree
    "load_codex_tree",
    "save_codex_tree",
    "save_codex_tree_to_json",
    # sync
    "sync_disk_to_db",
    "enrich_stories_with_book_metadata",
    "get_stories_at_path",
]
