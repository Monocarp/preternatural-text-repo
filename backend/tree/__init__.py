# backend/tree/__init__.py
"""
Tree module - Codex tree structure and operations.

This module handles the category/taxonomy tree:
- Loading from JSON or database
- Saving to JSON and database  
- Tree manipulation (assign, remove, find paths)
- Default category structure (CATEGORIES)
"""

from .operations import (
    CATEGORIES,
    merge_trees,
    assign_to_path,
    remove_from_path,
    find_paths_for_title,
)
from .persistence import (
    load_codex_tree,
    save_codex_tree,
    load_codex_tree_from_json,
    save_codex_tree_to_json,
)

__all__ = [
    # Constants
    "CATEGORIES",
    # Pure operations
    "merge_trees",
    "assign_to_path",
    "remove_from_path",
    "find_paths_for_title",
    # Persistence
    "load_codex_tree",
    "save_codex_tree",
    "load_codex_tree_from_json",
    "save_codex_tree_to_json",
]
