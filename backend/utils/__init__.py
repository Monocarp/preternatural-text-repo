from utils_legacy import *
from .rendering import render_md_with_scroll_and_highlight, render_static_story, find_book_slug
from .cache import invalidate_cache, get_cached_tree, get_book_metadata, clear_book_metadata_cache, preload_book_metadata, get_assigned_titles_set, rebuild_assigned_titles_cache, clear_assigned_titles_cache
from .storage import load_full_md, load_story_positions, save_story_positions, update_story_boundaries, load_pending_stories, save_pending_stories, check_story_overlap
from .export import export_stories, export_updated_jsons
from .tree_ops import CATEGORIES, merge_trees, remove_from_path, find_paths_for_title
# Import assign_to_path from utils_legacy which provides the stories_dict automatically
from utils_legacy import assign_to_path

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
]
