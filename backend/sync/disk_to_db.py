# backend/sync/disk_to_db.py
"""
Disk to database synchronization.

This module handles the heavy operation of syncing file data to the database.
Should only be called on server startup or explicit reload.
"""

import os
import json
import time
import logging
from datetime import datetime

from state import app_state
from models import Book, Story
from storage.books import load_story_positions

logger = logging.getLogger(__name__)


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


def sync_disk_to_db() -> None:
    """
    Heavy operation: Read all story_positions.json files and sync to database.
    
    This should only be called on server startup or explicit reload via /api/reload-stories.
    It updates:
    - stories_dict in memory
    - stories_dict.json on disk
    - Book and Story records in database
    """
    logger.info("Starting disk → DB sync...")
    start_time = time.monotonic()
    
    # First, sync book metadata from stories_meta.json files
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
            json.dump(app_state.stories_dict, f, indent=4, ensure_ascii=False)
        logger.info(f"Updated stories_dict.json with {len(app_state.stories_dict)} stories")
    except Exception as e:
        logger.error(f"Failed to write stories_dict.json: {e}")
    
    # If DB is enabled, sync disk → DB (upsert)
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            with app_state.SessionLocal() as db:
                books_synced = sync_books_from_metadata(db)
                logger.info(f"Synced {books_synced} books from metadata")
                
                # Build book_slug -> book_id mapping
                book_map = {book.slug: book.id for book in db.query(Book).all()}
                
                existing_story_ids = {s.id for s in db.query(Story).all()}
                
                for title, data in disk_stories.items():
                    story = db.query(Story).filter_by(title=title).first()
                    book_id = book_map.get(data["book_slug"])
                    
                    if story:
                        # Update existing story
                        story.book_slug = data["book_slug"]
                        story.book_id = book_id
                        story.pages = data["pages"]
                        story.keywords = data["keywords"]
                        story.start_char = data["start_char"]
                        story.end_char = data["end_char"]
                    else:
                        # Create new story
                        new_story = Story(**data, book_id=book_id)
                        db.add(new_story)
                        db.flush()
                
                db.commit()
                
                new_story_ids = {s.id for s in db.query(Story).all()}
                added_stories = new_story_ids - existing_story_ids
                
                if added_stories:
                    logger.info(f"Added {len(added_stories)} new stories to DB")
                
                elapsed = time.monotonic() - start_time
                logger.info(f"Synced {len(disk_stories)} stories from disk to DB in {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"DB sync failed: {e}")
    else:
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded {len(disk_stories)} stories from disk (no DB) in {elapsed:.2f}s")
