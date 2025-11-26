import logging
import time
import json
import os

# Import state for centralized globals
from state import app_state

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
def _get_load_codex_tree():
    from utils_legacy import load_codex_tree
    return load_codex_tree

def invalidate_cache():
    """Invalidate both tree and assigned titles caches."""
    app_state.last_data_change = time.monotonic()
    clear_assigned_titles_cache()
    logger.info(f"Cache invalidated at timestamp {app_state.last_data_change:.2f}")

def get_cached_tree():
    """Get tree from cache, reload if invalidated"""
    if app_state.tree_cache is None:
        logger.info("Loading tree for the first time")
        load_codex_tree = _get_load_codex_tree()
        app_state.tree_cache = load_codex_tree()
        app_state.cache_timestamp = time.monotonic()
    elif app_state.last_data_change > app_state.cache_timestamp:
        logger.info(f"Cache expired (last change: {app_state.last_data_change:.2f}, cache from: {app_state.cache_timestamp:.2f}), reloading tree")
        load_codex_tree = _get_load_codex_tree()
        app_state.tree_cache = load_codex_tree()
        app_state.cache_timestamp = time.monotonic()
    else:
        logger.debug(f"Using cached tree (age: {time.monotonic() - app_state.cache_timestamp:.2f}s)")
    
    return app_state.tree_cache

def get_book_metadata(book_slug):
    """Get book metadata with caching to avoid repeated DB queries"""
    if book_slug in app_state.book_metadata_cache:
        return app_state.book_metadata_cache[book_slug]
    
    book_info = {}
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            with app_state.SessionLocal() as db:
                from models import Book
                book = db.query(Book).filter_by(slug=book_slug).first()
                if book:
                    book_info = {
                        "book_title": book.title,
                        "book_author": book.author,
                        "book_year": book.year
                    }
        except Exception as e:
            logger.debug(f"Could not fetch book metadata for {book_slug}: {e}")
    
    app_state.book_metadata_cache[book_slug] = book_info
    return book_info

def clear_book_metadata_cache():
    """Clear the book metadata cache (call when books are updated)"""
    app_state.book_metadata_cache.clear()
    logger.info("Cleared book metadata cache")

def preload_book_metadata():
    """Preload all book metadata at startup to avoid any DB queries during search"""
    if not app_state.USE_DB or not app_state.SessionLocal:
        logger.info("No database - loading book metadata from stories_meta.json files")
        # Fallback: Load from JSON files
        try:
            for book_slug in os.listdir(app_state.books_dir):
                book_path = os.path.join(app_state.books_dir, book_slug)
                if os.path.isdir(book_path) and not book_slug.startswith('.'):
                    meta_path = os.path.join(book_path, "stories_meta.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                            app_state.book_metadata_cache[book_slug] = {
                                "book_title": meta.get("book_title", book_slug),
                                "book_author": meta.get("book_author", "Unknown"),
                                "book_year": meta.get("book_year", "")
                            }
                        except Exception as e:
                            logger.warning(f"Failed to load metadata from {meta_path}: {e}")
            logger.info(f"Loaded metadata from JSON files for {len(app_state.book_metadata_cache)} books")
        except Exception as e:
            logger.error(f"Failed to load book metadata from JSON: {e}")
        return
    
    # Database available - load from DB
    try:
        with app_state.SessionLocal() as db:
            from models import Book
            books = db.query(Book).all()
            for book in books:
                app_state.book_metadata_cache[book.slug] = {
                    "book_title": book.title,
                    "book_author": book.author,
                    "book_year": book.year
                }
        logger.info(f"Preloaded metadata from database for {len(app_state.book_metadata_cache)} books")
    except Exception as e:
        logger.error(f"Failed to preload book metadata from database: {e}")
        # Fallback to JSON if DB fails
        logger.info("Falling back to JSON files for book metadata")
        for book_slug in os.listdir(app_state.books_dir):
            book_path = os.path.join(app_state.books_dir, book_slug)
            if os.path.isdir(book_path) and not book_slug.startswith('.'):
                meta_path = os.path.join(book_path, "stories_meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        app_state.book_metadata_cache[book_slug] = {
                            "book_title": meta.get("book_title", book_slug),
                            "book_author": meta.get("book_author", "Unknown"),
                            "book_year": meta.get("book_year", "")
                        }
                    except Exception as e:
                        logger.warning(f"Failed to load metadata from {meta_path}: {e}")
        logger.info(f"Loaded metadata from JSON fallback for {len(app_state.book_metadata_cache)} books")

def get_assigned_titles_set():
    """Get cached set of assigned story titles, building if needed."""
    if app_state.assigned_titles_set is None:
        rebuild_assigned_titles_cache()
    return app_state.assigned_titles_set

def rebuild_assigned_titles_cache():
    """Rebuild the cache of assigned story titles by walking the codex tree."""
    tree = get_cached_tree()
    assigned = set()
    
    def walk(node):
        if isinstance(node, dict):
            if "_stories" in node:
                assigned.update(node["_stories"])
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            assigned.update(node)
    
    walk(tree)
    app_state.assigned_titles_set = assigned
    logger.info(f"Rebuilt assigned titles cache with {len(assigned)} titles")

def clear_assigned_titles_cache():
    """Clear the assigned titles cache."""
    app_state.assigned_titles_set = None
    logger.debug("Cleared assigned titles cache")