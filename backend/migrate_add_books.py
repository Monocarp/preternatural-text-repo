"""
Migration script to add Book table and populate it from stories_meta.json files.
Run this once to migrate existing data.

Usage:
    python migrate_add_books.py
"""

import os
import json
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Load environment
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(ROOT, '.env.local'))

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_PRISMA_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL not found in environment!")
    exit(1)

# Normalize postgres:// to postgresql://
if "postgres://" in DATABASE_URL and "postgresql://" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

BOOKS_DIR = os.path.join(ROOT, "books")

def create_books_table():
    """Create the books table if it doesn't exist"""
    logger.info("Creating books table...")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS books (
                id SERIAL PRIMARY KEY,
                slug VARCHAR(100) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                author VARCHAR(255),
                year VARCHAR(10),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Create index on slug for faster lookups
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_books_slug ON books(slug)
        """))
        
        conn.commit()
    logger.info("Books table created successfully")

def add_book_id_to_stories():
    """Add book_id column to stories table"""
    logger.info("Adding book_id column to stories table...")
    with engine.connect() as conn:
        # Check if column exists first
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='stories' AND column_name='book_id'
        """))
        
        if result.fetchone() is None:
            # Add the column
            conn.execute(text("""
                ALTER TABLE stories 
                ADD COLUMN book_id INTEGER REFERENCES books(id)
            """))
            logger.info("book_id column added successfully")
        else:
            logger.info("book_id column already exists")
        
        conn.commit()

def load_books_from_metadata():
    """Load book metadata from stories_meta.json files in each book folder"""
    books_data = []
    
    for folder in os.listdir(BOOKS_DIR):
        folder_path = os.path.join(BOOKS_DIR, folder)
        if not os.path.isdir(folder_path) or folder.startswith('.'):
            continue
        
        meta_path = os.path.join(folder_path, "stories_meta.json")
        if not os.path.exists(meta_path):
            logger.warning(f"No stories_meta.json found in {folder}, skipping")
            continue
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            # Use folder name as canonical slug (Option A)
            slug = folder
            title = meta.get("book_title", folder.replace('_', ' ').title())
            author = meta.get("book_author", "Unknown")
            year = meta.get("book_year", "")
            
            books_data.append({
                "slug": slug,
                "title": title,
                "author": author,
                "year": year
            })
            
            logger.info(f"Found book: {title} ({slug})")
            
        except Exception as e:
            logger.error(f"Error reading {meta_path}: {e}")
            continue
    
    return books_data

def populate_books_table(books_data):
    """Insert books into the database"""
    logger.info(f"Populating books table with {len(books_data)} books...")
    
    with SessionLocal() as db:
        from models import Book
        
        for book_data in books_data:
            # Check if book already exists
            existing = db.query(Book).filter_by(slug=book_data["slug"]).first()
            
            if existing:
                logger.info(f"Book {book_data['slug']} already exists, updating...")
                existing.title = book_data["title"]
                existing.author = book_data["author"]
                existing.year = book_data["year"]
                existing.updated_at = datetime.utcnow()
            else:
                logger.info(f"Creating book: {book_data['title']}")
                book = Book(
                    slug=book_data["slug"],
                    title=book_data["title"],
                    author=book_data["author"],
                    year=book_data["year"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(book)
        
        db.commit()
        logger.info("Books table populated successfully")

def link_stories_to_books():
    """Update story.book_id based on story.book_slug"""
    logger.info("Linking stories to books...")
    
    with SessionLocal() as db:
        from models import Story, Book
        
        # Get all books
        books = {book.slug: book.id for book in db.query(Book).all()}
        
        # Update all stories
        stories = db.query(Story).all()
        updated_count = 0
        
        for story in stories:
            book_id = books.get(story.book_slug)
            if book_id:
                story.book_id = book_id
                updated_count += 1
            else:
                logger.warning(f"No book found for story '{story.title}' with book_slug '{story.book_slug}'")
        
        db.commit()
        logger.info(f"Linked {updated_count} stories to books")

def verify_migration():
    """Verify that migration was successful"""
    logger.info("Verifying migration...")
    
    with SessionLocal() as db:
        from models import Book, Story
        
        book_count = db.query(Book).count()
        story_count = db.query(Story).count()
        linked_count = db.query(Story).filter(Story.book_id.isnot(None)).count()
        
        logger.info(f"Books in database: {book_count}")
        logger.info(f"Stories in database: {story_count}")
        logger.info(f"Stories linked to books: {linked_count}")
        
        # Show some examples
        sample_stories = db.query(Story).filter(Story.book_id.isnot(None)).limit(3).all()
        for story in sample_stories:
            logger.info(f"  Story: {story.title} -> Book: {story.book.title if story.book else 'None'}")
        
        if linked_count == story_count:
            logger.info("✓ Migration successful! All stories linked to books.")
        else:
            logger.warning(f"⚠ {story_count - linked_count} stories not linked to books")

def main():
    """Run the migration"""
    logger.info("=" * 60)
    logger.info("Starting Book Table Migration")
    logger.info("=" * 60)
    
    try:
        # Step 1: Create books table
        create_books_table()
        
        # Step 2: Add book_id column to stories
        add_book_id_to_stories()
        
        # Step 3: Load book metadata from files
        books_data = load_books_from_metadata()
        
        if not books_data:
            logger.error("No book metadata found! Check your stories_meta.json files.")
            return
        
        # Step 4: Populate books table
        populate_books_table(books_data)
        
        # Step 5: Link stories to books
        link_stories_to_books()
        
        # Step 6: Verify
        verify_migration()
        
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
