"""
Book Ingestion Script - Consumes Stories.md + stories_meta.json for new books

This script reads the extracted stories from your pre-processing Colab notebook
and ingests them into the database. It handles both Book metadata and Story content.

Usage:
    # Ingest a single book (folder name must match stories_meta.json slug)
    python ingest_book.py christian_mysticism_vol_iv
    
    # Ingest all books with stories_meta.json
    python ingest_book.py --all
"""

import os
import sys
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Load environment and models
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'backend'))

load_dotenv(dotenv_path=os.path.join(ROOT, '.env.local'))

from models import engine, Book, Story
SessionLocal = sessionmaker(bind=engine)

BOOKS_DIR = os.path.join(ROOT, "books")


def parse_stories_md(md_path: Path):
    """
    Parse Stories.md to extract individual story objects.
    Format expected:
    <div align="center"><b>Story Title</b></div>
    <div align="center">"Book Title" Pages X-Y</div>
    
    Story content here...
    """
    content = md_path.read_text(encoding='utf-8')
    
    # Split on story headers (the bold centered div tags)
    # Pattern: <div align="center"><b>TITLE</b></div>
    story_pattern = r'<div align="center"><b>(.*?)</b></div>\s*<div align="center">"(.*?)" Pages (.*?)</div>\s*(.*?)(?=<div align="center"><b>|$)'
    
    matches = re.findall(story_pattern, content, re.DOTALL)
    
    stories = []
    for match in matches:
        title, book_title, pages, body = match
        title = title.strip()
        pages = pages.strip()
        body = body.strip()
        
        stories.append({
            "title": title,
            "pages": pages,
            "content": body
        })
    
    logger.info(f"Parsed {len(stories)} stories from {md_path}")
    return stories


def ingest_book(book_slug: str, dry_run: bool = False):
    """
    Ingest a single book from its folder.
    
    Args:
        book_slug: Folder name (e.g., 'christian_mysticism_vol_iv')
        dry_run: If True, don't commit changes to database
    """
    book_path = Path(BOOKS_DIR) / book_slug
    
    if not book_path.exists():
        logger.error(f"Book folder not found: {book_path}")
        return False
    
    # Load metadata
    meta_path = book_path / "stories_meta.json"
    if not meta_path.exists():
        logger.error(f"stories_meta.json not found in {book_path}")
        return False
    
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    logger.info(f"Loading book: {meta.get('book_title', book_slug)}")
    
    # Load Stories.md
    stories_md_path = book_path / "Stories.md"
    if not stories_md_path.exists():
        logger.error(f"Stories.md not found in {book_path}")
        return False
    
    parsed_stories = parse_stories_md(stories_md_path)
    
    # Load story_positions.json for character offsets
    positions_path = book_path / "story_positions.json"
    if not positions_path.exists():
        logger.error(f"story_positions.json not found in {book_path}")
        return False
    
    positions = json.loads(positions_path.read_text(encoding='utf-8'))
    
    # Load Full_Text.md to get total length
    full_text_path = book_path / "Full_Text.md"
    if full_text_path.exists():
        full_text = full_text_path.read_text(encoding='utf-8')
        text_length = len(full_text)
        logger.info(f"Full_Text.md length: {text_length} characters")
    else:
        text_length = 0
        logger.warning("Full_Text.md not found, using 0 for end_char defaults")
    
    if dry_run:
        logger.info("DRY RUN - Changes will not be committed")
    
    # Start database transaction
    with SessionLocal() as db:
        # 1. Upsert Book
        book = db.query(Book).filter_by(slug=book_slug).first()
        
        if book:
            logger.info(f"Updating existing book: {meta['book_title']}")
            book.title = meta['book_title']
            book.author = meta.get('book_author', 'Unknown')
            book.year = meta.get('book_year', '')
            book.updated_at = datetime.utcnow()
        else:
            logger.info(f"Creating new book: {meta['book_title']}")
            book = Book(
                slug=book_slug,
                title=meta['book_title'],
                author=meta.get('book_author', 'Unknown'),
                year=meta.get('book_year', ''),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(book)
        
        db.flush()  # Get book.id
        logger.info(f"Book ID: {book.id}")
        
        # 2. Ingest stories
        story_count = 0
        updated_count = 0
        created_count = 0
        
        for parsed_story in parsed_stories:
            title = parsed_story['title']
            pages = parsed_story['pages']
            
            # Get position data
            pos_data = positions.get(title, {})
            start_char = pos_data.get('start_char', 0)
            end_char = pos_data.get('end_char', text_length)
            keywords = ', '.join(pos_data.get('keywords', []))
            
            # Check if story exists
            story = db.query(Story).filter_by(title=title).first()
            
            if story:
                # Update existing story
                logger.debug(f"Updating story: {title}")
                story.book_slug = book_slug
                story.book_id = book.id
                story.pages = pages
                story.keywords = keywords
                story.start_char = start_char
                story.end_char = end_char
                updated_count += 1
            else:
                # Create new story
                logger.debug(f"Creating story: {title}")
                story = Story(
                    title=title,
                    book_slug=book_slug,
                    book_id=book.id,
                    pages=pages,
                    keywords=keywords,
                    start_char=start_char,
                    end_char=end_char
                )
                db.add(story)
                created_count += 1
            
            story_count += 1
        
        if not dry_run:
            db.commit()
            logger.info(f"✓ Committed changes to database")
        else:
            db.rollback()
            logger.info(f"✗ Rolled back (dry run)")
        
        logger.info(f"Ingestion complete:")
        logger.info(f"  Book: {book.title} (ID: {book.id})")
        logger.info(f"  Stories processed: {story_count}")
        logger.info(f"  Stories created: {created_count}")
        logger.info(f"  Stories updated: {updated_count}")
        
        return True


def ingest_all_books(dry_run: bool = False):
    """Ingest all books that have stories_meta.json"""
    books_dir = Path(BOOKS_DIR)
    
    if not books_dir.exists():
        logger.error(f"Books directory not found: {books_dir}")
        return
    
    book_folders = [
        f for f in books_dir.iterdir() 
        if f.is_dir() and not f.name.startswith('.') and (f / "stories_meta.json").exists()
    ]
    
    logger.info(f"Found {len(book_folders)} books to ingest")
    
    success_count = 0
    for book_folder in book_folders:
        logger.info("=" * 60)
        if ingest_book(book_folder.name, dry_run=dry_run):
            success_count += 1
        logger.info("")
    
    logger.info("=" * 60)
    logger.info(f"Ingestion complete: {success_count}/{len(book_folders)} books processed successfully")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest books from Stories.md + stories_meta.json")
    parser.add_argument('book_slug', nargs='?', help='Book folder name (e.g., christian_mysticism_vol_iv)')
    parser.add_argument('--all', action='store_true', help='Ingest all books with stories_meta.json')
    parser.add_argument('--dry-run', action='store_true', help='Parse but do not commit to database')
    
    args = parser.parse_args()
    
    if args.all:
        ingest_all_books(dry_run=args.dry_run)
    elif args.book_slug:
        ingest_book(args.book_slug, dry_run=args.dry_run)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python ingest_book.py christian_mysticism_vol_iv")
        print("  python ingest_book.py --all")
        print("  python ingest_book.py --all --dry-run")


if __name__ == "__main__":
    main()
