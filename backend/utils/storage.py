"""
Storage module - File I/O operations for story positions and full text.

Re-exports from utils_legacy.py to provide a clean module interface.
The actual implementations remain in utils_legacy to avoid circular import issues.
"""

# Re-export storage functions from utils_legacy
from utils_legacy import (
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

__all__ = [
    "load_full_md",
    "load_story_positions",
    "save_story_positions",
    "update_story_boundaries",
    "update_story_title",
    "update_story_keywords",
    "load_pending_stories",
    "save_pending_stories",
    "check_story_overlap",
]
