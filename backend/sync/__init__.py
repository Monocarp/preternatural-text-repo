# backend/sync/__init__.py
"""
Sync module - Database and GitHub synchronization operations.

Handles syncing data between:
- Disk files and database (disk_to_db)
- Local files and GitHub repository (github_sync)
"""

from .disk_to_db import (
    sync_disk_to_db,
    sync_books_from_metadata,
    load_all_stories,
    enrich_stories_with_book_metadata,
    get_stories_at_path,
)

from .github_sync import (
    get_github_config,
    sync_file_to_github,
    sync_codex_tree,
    sync_stories_dict,
    sync_story_positions,
    sync_all_changed_files,
    on_story_boundary_change,
    on_story_title_change,
    on_story_added,
    on_story_deleted,
    on_category_change,
)

__all__ = [
    # Disk to DB sync
    "sync_disk_to_db",
    "sync_books_from_metadata",
    "load_all_stories",
    "enrich_stories_with_book_metadata",
    "get_stories_at_path",
    # GitHub sync
    "get_github_config",
    "sync_file_to_github",
    "sync_codex_tree",
    "sync_stories_dict",
    "sync_story_positions",
    "sync_all_changed_files",
    "on_story_boundary_change",
    "on_story_title_change",
    "on_story_added",
    "on_story_deleted",
    "on_category_change",
]
