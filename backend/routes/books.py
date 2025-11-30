# backend/routes/books.py
"""
Book routes for the Lexicon API.

Endpoints:
- GET /api/books - List all books with story counts
- GET /api/books/{slug} - Get single book details
- GET /api/full-text/{book_slug} - Get book full text
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from .dependencies import BookResponse
from models import SessionLocal, Book
from utils import load_full_md

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["books"])


@router.get("/books", response_model=List[BookResponse])
def get_books():
    """Get all books with story counts."""
    try:
        with SessionLocal() as db:
            books = db.query(Book).all()
            result = []
            for book in books:
                result.append({
                    "id": book.id,
                    "slug": book.slug,
                    "title": book.title,
                    "author": book.author,
                    "year": book.year,
                    "story_count": len(book.stories) if book.stories else 0
                })
            return result
    except Exception as e:
        log.error(f"Failed to fetch books: {e}")
        raise HTTPException(500, f"Failed to fetch books: {str(e)}")


@router.get("/books/{slug}")
def get_book(slug: str, include_stories: bool = False):
    """
    Get a single book by slug.
    
    Args:
        slug: Book slug (e.g. "operation_trojan_horse")
        include_stories: If True, include list of stories with their metadata
    """
    try:
        with SessionLocal() as db:
            book = db.query(Book).filter_by(slug=slug).first()
            if not book:
                raise HTTPException(404, f"Book not found: {slug}")
            
            result = {
                "id": book.id,
                "slug": book.slug,
                "title": book.title,
                "author": book.author,
                "year": book.year,
                "story_count": len(book.stories) if book.stories else 0
            }
            
            if include_stories:
                result["stories"] = [
                    {
                        "title": story.title,
                        "pages": story.pages,
                        "keywords": story.keywords,
                        "start_char": story.start_char,
                        "end_char": story.end_char
                    }
                    for story in book.stories
                ]
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to fetch book {slug}: {e}")
        raise HTTPException(500, f"Failed to fetch book: {str(e)}")


@router.get("/full-text/{book_slug}")
def get_full_text(book_slug: str):
    """
    Get full markdown text for a book.
    
    Returns the complete Full_Text.md content and its length.
    """
    try:
        full_text = load_full_md(book_slug)
        return {"text": full_text, "length": len(full_text)}
    except Exception as e:
        log.error(f"Failed to load full text for {book_slug}: {e}")
        raise HTTPException(404, f"Book not found: {book_slug}")
