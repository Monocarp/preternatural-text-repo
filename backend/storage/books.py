# backend/storage/books.py
"""
Book file I/O operations.

Handles loading and saving book-related files:
- Full_Text.md (source text)
- story_positions.json (story boundaries)
"""

import os
import json
import logging
from functools import lru_cache

from state import app_state

logger = logging.getLogger(__name__)


@lru_cache(maxsize=10)
def _load_full_md_cached(book_slug: str, books_dir: str) -> str:
    """
    Internal cached loader for Full_Text.md.
    
    Uses books_dir as parameter to make cache key unique per directory.
    """
    md_path = os.path.join(books_dir, book_slug, "Full_Text.md")
    try:
        with open(md_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        logger.debug(f"Loaded Full_Text.md for {book_slug}, length: {len(content)}")
        return content
    except Exception as e:
        logger.error(f"Failed to load Full_Text.md for {book_slug}: {e}")
        return ""


def load_full_md(book_slug: str) -> str:
    """
    Load Full_Text.md for a book, with LRU caching.
    
    Caches up to 10 most recently accessed books in memory.
    
    Args:
        book_slug: The book identifier (directory name)
    
    Returns:
        The full markdown text content
    """
    return _load_full_md_cached(book_slug, app_state.books_dir)


def clear_full_md_cache():
    """Clear the full text cache. Call after modifying Full_Text.md files."""
    _load_full_md_cached.cache_clear()
    logger.info("Full text cache cleared")


def get_full_md_cache_info():
    """Get cache statistics for debugging."""
    return _load_full_md_cached.cache_info()


def load_story_positions(book_slug: str) -> dict:
    """
    Load story_positions.json for a book, with caching.
    
    Args:
        book_slug: The book identifier (directory name)
    
    Returns:
        Dictionary mapping story titles to their position data
        {title: {start_char, end_char, pages, keywords, ...}}
    """
    if book_slug not in app_state.story_positions:
        pos_path = os.path.join(app_state.books_dir, book_slug, "story_positions.json")
        try:
            with open(pos_path, "r", encoding="utf-8-sig") as f:
                app_state.story_positions[book_slug] = json.load(f)
            logger.debug(
                f"Loaded story_positions for {book_slug} "
                f"with {len(app_state.story_positions[book_slug])} entries"
            )
        except Exception as e:
            logger.error(f"Failed to load story_positions.json for {book_slug}: {e}")
            app_state.story_positions[book_slug] = {}
    
    return app_state.story_positions[book_slug]


def save_story_positions(book_slug: str) -> bool:
    """
    Save story positions to JSON file.
    
    Args:
        book_slug: The book identifier (directory name)
    
    Returns:
        True if save succeeded, False otherwise
    """
    pos_path = os.path.join(app_state.books_dir, book_slug, "story_positions.json")
    try:
        with open(pos_path, "w", encoding="utf-8") as f:
            json.dump(app_state.story_positions[book_slug], f, indent=4, ensure_ascii=False)
        logger.info(f"Saved story_positions for {book_slug}")
        return True
    except Exception as e:
        logger.error(f"Failed to save story_positions.json for {book_slug}: {e}")
        return False
