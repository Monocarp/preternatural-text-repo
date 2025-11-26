# backend/storage/__init__.py
"""
Storage module - File I/O operations for books, stories, and pending queue.

This module handles all disk operations:
- Loading/saving book full text and story positions
- Updating story boundaries and titles
- Managing the pending stories queue
"""

from .books import (
    load_full_md,
    load_story_positions,
    save_story_positions,
    clear_full_md_cache,
    get_full_md_cache_info,
)
from .stories import (
    update_story_boundaries,
    update_story_title,
)
from .pending import (
    load_pending_stories,
    save_pending_stories,
    check_story_overlap,
)

__all__ = [
    # Book operations
    "load_full_md",
    "load_story_positions",
    "save_story_positions",
    "clear_full_md_cache",
    "get_full_md_cache_info",
    # Story operations
    "update_story_boundaries",
    "update_story_title",
    # Pending queue
    "load_pending_stories",
    "save_pending_stories",
    "check_story_overlap",
]
