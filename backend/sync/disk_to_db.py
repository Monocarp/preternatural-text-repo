# backend/sync/disk_to_db.py
"""
Disk to database synchronization.

This module handles the heavy operation of syncing file data to the database.
Should only be called on server startup or explicit reload.
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime

from state import app_state
from models import Book, Story
from storage.books import load_story_positions

logger = logging.getLogger(__name__)


def cleanup_orphaned_node_stories(db) -> int:
    """
    Remove NodeStory entries that reference non-existent stories.
    
    This handles cases where stories were deleted but their category
    assignments (NodeStory) remain.
    
    Args:
        db: Database session
    
    Returns:
        Number of orphaned entries deleted
    """
    from models import NodeStory, Story
    
    # Find NodeStory entries that reference non-existent story IDs
    valid_story_ids = {s.id for s in db.query(Story.id).all()}
    
    orphaned = db.query(NodeStory).filter(
        ~NodeStory.story_id.in_(valid_story_ids)
    ).all()
    
    if orphaned:
        for ns in orphaned:
            db.delete(ns)
        db.commit()
        logger.info(f"Deleted {len(orphaned)} orphaned NodeStory entries")
        return len(orphaned)
    
    return 0


def load_all_stories() -> dict:
    """
    Load all stories from story_positions.json files across all books.
    
    Returns:
        Dictionary mapping story titles to story data
    """
    stories = {}
    
    for book_slug in os.listdir(app_state.books_dir):
        book_path = os.path.join(app_state.books_dir, book_slug)
        if os.path.isdir(book_path) and not book_slug.startswith('.'):
            positions = load_story_positions(book_slug)
            
            for title, details in positions.items():
                stories[title] = {
                    "title": title,
                    "book_slug": book_slug,
                    "pages": details.get("pages", ""),
                    "keywords": ', '.join(details.get("keywords", [])),
                    "start_char": details.get("start_char", 0),
                    "end_char": details.get("end_char", 0)
                }
    
    logger.info(f"Loaded {len(stories)} stories from story_positions.json across books")
    return stories


def enrich_stories_with_book_metadata(stories: list) -> list:
    """
    Add book metadata (title, author, year) to story objects using preloaded cache.
    
    Args:
        stories: List of story dictionaries
    
    Returns:
        List of enriched story dictionaries
    """
    enriched = []
    
    for story in stories:
        enriched_story = story.copy()
        book_slug = story.get('book_slug')
        
        # Use the preloaded cache
        if book_slug and book_slug in app_state.book_metadata_cache:
            book_meta = app_state.book_metadata_cache[book_slug]
            enriched_story['book_title'] = book_meta.get('book_title', book_slug)
            enriched_story['book_author'] = book_meta.get('book_author', 'Unknown')
            enriched_story['book_year'] = book_meta.get('book_year', '')
        else:
            # Fallback: use book_slug as title if not in cache
            logger.debug(f"Book metadata not found in cache for {book_slug}")
            enriched_story['book_title'] = book_slug.replace('_', ' ').title() if book_slug else 'Unknown'
            enriched_story['book_author'] = 'Unknown'
            enriched_story['book_year'] = ''
        
        enriched.append(enriched_story)
    
    return enriched


def get_stories_at_path(tree: dict, path: list) -> list:
    """
    Get stories at a given path in the tree.
    
    Traverses the tree to the specified path and collects all stories
    at or below that level.
    
    Args:
        tree: The codex tree dictionary
        path: List of path segments to traverse
    
    Returns:
        List of enriched story dictionaries
    """
    logger.debug(f"get_stories_at_path called with path: {path}")
    
    current = tree
    for level in path:
        logger.debug(f"Looking for level '{level}' in current keys")
        if level not in current:
            logger.debug(f"Level '{level}' not found in tree")
            return []
        current = current[level]
    
    # Collect ALL stories at or below this level
    titles = []
    
    def recurse(node):
        if isinstance(node, list):
            titles.extend(node)
            logger.debug(f"Found story list: {node}")
        elif isinstance(node, dict):
            if '_stories' in node:
                titles.extend(node['_stories'])
                logger.debug(f"Found _stories: {node['_stories']}")
            for key, value in node.items():
                if key != '_stories':
                    recurse(value)
    
    recurse(current)
    logger.debug(f"Total titles collected: {titles}")
    
    # Resolve to full story objects
    unique_titles = set(titles)
    result = [
        app_state.stories_dict[title]
        for title in unique_titles
        if title in app_state.stories_dict
    ]
    logger.debug(f"Returning {len(result)} stories")
    
    return enrich_stories_with_book_metadata(result)


def sync_books_from_metadata(db) -> int:
    """
    Sync Book records from stories_meta.json files in book folders.
    
    Args:
        db: Database session
    
    Returns:
        Count of books synced
    """
    synced_count = 0
    
    for folder in os.listdir(app_state.books_dir):
        folder_path = os.path.join(app_state.books_dir, folder)
        if not os.path.isdir(folder_path) or folder.startswith('.'):
            continue
        
        meta_path = os.path.join(folder_path, "stories_meta.json")
        if not os.path.exists(meta_path):
            logger.debug(f"No stories_meta.json in {folder}")
            continue
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            slug = folder
            title = meta.get("book_title", folder.replace('_', ' ').title())
            author = meta.get("book_author", "Unknown")
            year = meta.get("book_year", "")
            
            # Upsert book
            book = db.query(Book).filter_by(slug=slug).first()
            if book:
                book.title = title
                book.author = author
                book.year = year
                book.updated_at = datetime.utcnow()
            else:
                book = Book(
                    slug=slug,
                    title=title,
                    author=author,
                    year=year,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(book)
            db.flush()
            synced_count += 1
            
        except Exception as e:
            logger.error(f"Error syncing book metadata from {meta_path}: {e}")
            continue
    
    return synced_count


def _compute_disk_hash() -> str:
    """
    Compute a hash of all story_positions.json + stories_meta.json files.
    If the hash matches the last boot, we can skip the expensive DB sync.
    """
    h = hashlib.sha256()
    for book_slug in sorted(os.listdir(app_state.books_dir)):
        book_path = os.path.join(app_state.books_dir, book_slug)
        if not os.path.isdir(book_path) or book_slug.startswith('.'):
            continue
        for fname in ("story_positions.json", "stories_meta.json"):
            fpath = os.path.join(book_path, fname)
            if os.path.exists(fpath):
                h.update(fpath.encode())
                with open(fpath, "rb") as f:
                    h.update(f.read())
    return h.hexdigest()


_HASH_FILE = "sync_hash.txt"


def sync_disk_to_db() -> None:
    """
    Heavy operation: Read all story_positions.json files and sync to database.
    
    This should only be called on server startup or explicit reload via /api/reload-stories.
    It updates:
    - stories_dict in memory
    - stories_dict.json on disk
    - Book and Story records in database
    
    Optimizations:
    - Skips entirely if disk files haven't changed since last boot (hash check)
    - Uses bulk SQL upserts instead of per-row SELECT+INSERT/UPDATE
    """
    logger.info("Starting disk → DB sync...")
    start_time = time.monotonic()
    
    # --- Hash check: skip sync if nothing changed ---
    hash_path = os.path.join(str(app_state.data_dir), _HASH_FILE)
    current_hash = _compute_disk_hash()
    try:
        if os.path.exists(hash_path):
            with open(hash_path, "r") as f:
                stored_hash = f.read().strip()
            if stored_hash == current_hash:
                # Data unchanged — still need to populate in-memory stories_dict
                disk_stories = load_all_stories()
                app_state.stories_dict.clear()
                app_state.stories_dict.update(disk_stories)
                elapsed = time.monotonic() - start_time
                logger.info(
                    f"Disk hash unchanged — skipped DB sync. "
                    f"Loaded {len(disk_stories)} stories into memory in {elapsed:.2f}s"
                )
                return
    except Exception as e:
        logger.warning(f"Hash check failed, proceeding with full sync: {e}")
    
    # --- Full sync path (hash changed or first boot) ---
    
    # Sync book metadata from stories_meta.json files
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            with app_state.SessionLocal() as db:
                for book_slug in os.listdir(app_state.books_dir):
                    book_path = os.path.join(app_state.books_dir, book_slug)
                    if os.path.isdir(book_path) and not book_slug.startswith('.'):
                        meta_path = os.path.join(book_path, "stories_meta.json")
                        if os.path.exists(meta_path):
                            try:
                                with open(meta_path, "r", encoding="utf-8") as f:
                                    meta = json.load(f)
                                
                                book = db.query(Book).filter_by(slug=book_slug).first()
                                if book:
                                    book.title = meta.get("book_title", book_slug)
                                    book.author = meta.get("book_author", "Unknown")
                                    book.year = meta.get("book_year", "")
                                else:
                                    book = Book(
                                        slug=book_slug,
                                        title=meta.get("book_title", book_slug),
                                        author=meta.get("book_author", "Unknown"),
                                        year=meta.get("book_year", "")
                                    )
                                    db.add(book)
                                logger.info(f"Synced book metadata for '{book_slug}'")
                            except Exception as e:
                                logger.warning(f"Failed to load stories_meta.json for {book_slug}: {e}")
                db.commit()
                logger.info("Book metadata sync complete")
        except Exception as e:
            logger.error(f"Failed to sync book metadata: {e}")
    
    # Load all stories from disk (source of truth)
    disk_stories = load_all_stories()
    
    # Update in-place to preserve references
    app_state.stories_dict.clear()
    app_state.stories_dict.update(disk_stories)
    
    # Write stories_dict.json for consistency
    try:
        with open(app_state.stories_dict_path, "w", encoding="utf-8") as f:
            json.dump(app_state.stories_dict, f, indent=4, ensure_ascii=False, sort_keys=True)
        logger.info(f"Updated stories_dict.json with {len(app_state.stories_dict)} stories")
    except Exception as e:
        logger.error(f"Failed to write stories_dict.json: {e}")
    
    # If DB is enabled, sync disk → DB (bulk upsert)
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            
            with app_state.SessionLocal() as db:
                books_synced = sync_books_from_metadata(db)
                logger.info(f"Synced {books_synced} books from metadata")
                
                # Build book_slug -> book_id mapping
                book_map = {book.slug: book.id for book in db.query(Book).all()}
                
                # --- Bulk upsert all stories in one statement ---
                if disk_stories:
                    rows = []
                    for title, data in disk_stories.items():
                        rows.append({
                            "title": title,
                            "book_slug": data["book_slug"],
                            "book_id": book_map.get(data["book_slug"]),
                            "pages": data["pages"],
                            "keywords": data["keywords"],
                            "start_char": data["start_char"],
                            "end_char": data["end_char"],
                        })
                    
                    stmt = pg_insert(Story.__table__).values(rows)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["title"],
                        set_={
                            "book_slug": stmt.excluded.book_slug,
                            "book_id": stmt.excluded.book_id,
                            "pages": stmt.excluded.pages,
                            "keywords": stmt.excluded.keywords,
                            "start_char": stmt.excluded.start_char,
                            "end_char": stmt.excluded.end_char,
                        }
                    )
                    db.execute(stmt)
                    db.commit()
                    logger.info(f"Bulk upserted {len(rows)} stories")
                
                # DELETE stories from DB that are no longer on disk (critical for sync!)
                disk_titles = set(disk_stories.keys())
                orphaned = db.query(Story).filter(~Story.title.in_(disk_titles)).all()
                
                if orphaned:
                    orphaned_titles = [s.title for s in orphaned]
                    for story in orphaned:
                        db.delete(story)
                    db.commit()
                    logger.info(f"Deleted {len(orphaned)} orphaned stories from DB: {orphaned_titles}")
                    
                    # Also cleanup any orphaned NodeStory entries
                    cleanup_orphaned_node_stories(db)
                
                elapsed = time.monotonic() - start_time
                logger.info(f"Synced {len(disk_stories)} stories from disk to DB in {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"DB sync failed: {e}", exc_info=True)
    else:
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded {len(disk_stories)} stories from disk (no DB) in {elapsed:.2f}s")
    
    # Save hash so next boot can skip sync if nothing changed
    try:
        with open(hash_path, "w") as f:
            f.write(current_hash)
    except Exception as e:
        logger.warning(f"Failed to save sync hash: {e}")
