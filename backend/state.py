# backend/state.py
"""
Centralized application state for the Preternatural Text backend.

This module holds all global state that was previously scattered across utils_legacy.py.
By centralizing state, we can:
1. Split functions into separate modules without circular imports
2. Better understand data flow and dependencies
3. Easier testing via state injection

Usage:
    from state import app_state
    
    # Access state
    app_state.stories_dict["my_story"] = {...}
    tree = app_state.tree_cache
    
    # State is initialized once at module load, then populated by utils_legacy
"""

import logging
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

# Compute absolute paths - works from any working directory
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent

# Load environment before anything else
load_dotenv(dotenv_path=ROOT_DIR / '.env.local')

logger = logging.getLogger(__name__)


class AppState:
    """
    Singleton container for all application state.
    
    Attributes are grouped by purpose:
    - Paths: File system locations
    - Database: DB connection state
    - Caches: In-memory data caches
    - Search: Haystack pipelines and document store
    """
    
    def __init__(self):
        # ------------------------------------------------------------------ #
        # Paths (absolute, using pathlib)
        # ------------------------------------------------------------------ #
        self.books_dir = ROOT_DIR / "books"
        self.data_dir = ROOT_DIR / "data"
        self.document_store_path = self.data_dir / "document_store.json"
        self.codex_tree_path = self.data_dir / "codex_tree.json"
        self.stories_dict_path = self.data_dir / "stories_dict.json"
        self.pending_stories_path = self.data_dir / "pending_stories.json"
        
        # ------------------------------------------------------------------ #
        # Database connection state
        # ------------------------------------------------------------------ #
        import os
        self.DB_URL: Optional[str] = os.getenv("POSTGRES_PRISMA_URL")
        self.USE_DB: bool = False
        self.engine: Any = None
        self.SessionLocal: Any = None
        
        # ------------------------------------------------------------------ #
        # Tree cache (used by utils/cache.py)
        # ------------------------------------------------------------------ #
        self.tree_cache: Any = None
        self.cache_timestamp: float = 0
        self.last_data_change: float = 0
        
        # ------------------------------------------------------------------ #
        # Story/book data caches
        # ------------------------------------------------------------------ #
        self.stories_dict: dict = {}           # {story_title: story_data}
        self.book_metadata_cache: dict = {}    # {book_slug: {title, description, ...}}
        self.full_mds: dict = {}               # {book_slug: full_text_content}
        self.story_positions: dict = {}        # {book_slug: {title: {start_char, end_char}}}
        
        # ------------------------------------------------------------------ #
        # Book discovery
        # ------------------------------------------------------------------ #
        self.books: list = []                  # List of book directory names
        self.sources: list = []                # ["All Sources"] + sorted books
        self.book_dir_to_slug: dict = {}       # {dir_name: book_slug}
        
        # ------------------------------------------------------------------ #
        # Assigned titles cache (used by utils/cache.py)
        # ------------------------------------------------------------------ #
        self.assigned_titles_set: Optional[set] = None
        
        # ------------------------------------------------------------------ #
        # Haystack search components (initialized by utils_legacy)
        # ------------------------------------------------------------------ #
        self.document_store: Any = None
        self.MODEL_PATH: str = ""
        
        # Embedders
        self.embedder_both: Any = None        # Text embedder for hybrid pipeline
        self.embedder_sem: Any = None         # Text embedder for semantic pipeline
        self.embedder_doc: Any = None         # Document embedder for indexing
        
        # Retrievers
        self.retriever_embedding_both: Any = None
        self.retriever_bm25_both: Any = None
        self.retriever_bm25_key: Any = None
        self.retriever_embedding_sem: Any = None
        
        # Pipelines
        self.both_pipeline: Any = None        # Hybrid search
        self.keyword_pipeline: Any = None     # BM25 only
        self.semantic_pipeline: Any = None    # Embedding only
        
        # Discover books on init
        self.discover_books()
        
        logger.debug("AppState initialized")
    
    def init_database(self):
        """Initialize database connection if URL is provided."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models import Base
        
        if self.DB_URL:
            db_url = self.DB_URL
            if "postgres" in db_url:
                db_url = db_url.replace("postgres://", "postgresql://")
            try:
                self.engine = create_engine(db_url)
                self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
                Base.metadata.create_all(bind=self.engine)
                self.USE_DB = True
                logger.info("Database connection established")
            except Exception as e:
                logger.warning(f"Failed to connect to database: {e}. Falling back to JSON storage.")
                self.USE_DB = False
        else:
            logger.info("No database URL provided. Using JSON storage.")
    
    def discover_books(self):
        """Discover available books from the books directory."""
        import json
        
        self.books = []
        self.book_dir_to_slug = {}
        
        if not self.books_dir.exists():
            logger.warning(f"Books directory not found: {self.books_dir}")
            self.sources = ["All Sources"]
            return
        
        for entry in self.books_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith('.'):
                d = entry.name
                self.books.append(d)
                
                # Load stories_meta.json to get the actual book_slug
                meta_path = entry / "stories_meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        book_slug = meta.get("book_slug", d)
                        self.book_dir_to_slug[d] = book_slug
                        logger.debug(f"Mapped directory '{d}' to book slug '{book_slug}'")
                    except Exception as e:
                        logger.warning(f"Could not load stories_meta.json for {d}: {e}")
                        self.book_dir_to_slug[d] = d
                else:
                    self.book_dir_to_slug[d] = d
        
        self.sources = ["All Sources"] + sorted(self.books)
        logger.info(f"Discovered books: {self.sources}")
        logger.info(f"Book directory to slug mapping: {self.book_dir_to_slug}")


# Global singleton instance
app_state = AppState()
