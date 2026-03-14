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
import os
import shutil
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
        
        # Support custom data directory (for Render persistent disk)
        data_dir_override = os.getenv("DATA_DIR")
        if data_dir_override:
            self.data_dir = Path(data_dir_override)
            logger.info(f"Using custom DATA_DIR: {self.data_dir}")
        else:
            self.data_dir = ROOT_DIR / "data"
        
        self.seeds_dir = ROOT_DIR / "data" / "seeds"  # Seeds always in repo
        self.document_store_path = self.data_dir / "document_store.json"
        self.codex_tree_path = self.data_dir / "codex_tree.json"
        self.stories_dict_path = self.data_dir / "stories_dict.json"
        self.pending_stories_path = self.data_dir / "pending_stories.json"
        
        # ------------------------------------------------------------------ #
        # Database connection state
        # ------------------------------------------------------------------ #
        # Check multiple possible env var names (Vercel uses NEON_ prefix)
        self.DB_URL: Optional[str] = (
            os.getenv("DATABASE_URL") or 
            os.getenv("POSTGRES_PRISMA_URL") or
            os.getenv("NEON_DATABASE_URL") or
            os.getenv("NEON_POSTGRES_PRISMA_URL")
        )
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
        
        # Initialize database connection
        self.init_database()
        
        # Initialize data files from seeds if needed (for fresh deploys)
        self.initialize_data_files()
        
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
                self.engine = create_engine(
                    db_url,
                    pool_pre_ping=True,  # Test connections before using them
                    pool_recycle=300,    # Recycle connections after 5 minutes (serverless friendly)
                    pool_size=2,         # Keep minimal idle connections
                    max_overflow=3       # Allow up to 5 total if needed
                )
                self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
                Base.metadata.create_all(bind=self.engine)
                self.USE_DB = True
                logger.info("Database connection established")
            except Exception as e:
                logger.warning(f"Failed to connect to database: {e}. Falling back to JSON storage.")
                self.USE_DB = False
        else:
            logger.info("No database URL provided. Using JSON storage.")
    
    def initialize_data_files(self):
        """
        Initialize data files from seed copies if they don't exist.
        
        This is critical for fresh deployments where the persistent disk is empty.
        Seed files are tracked in git (data/seeds/), but the main data files are NOT
        tracked - they live only on the persistent disk.
        
        Mapping:
            seeds/codex_tree.seed.json    -> data/codex_tree.json
            seeds/stories_dict.seed.json  -> data/stories_dict.json
            seeds/pending_stories.seed.json -> data/pending_stories.json
            seeds/stories.faiss           -> data/stories.faiss
            seeds/stories.faiss.map.json  -> data/stories.faiss.map.json
        """
        # Define seed -> target mappings
        seed_mappings = [
            ("codex_tree.seed.json", "codex_tree.json"),
            ("stories_dict.seed.json", "stories_dict.json"),
            ("pending_stories.seed.json", "pending_stories.json"),
            ("stories.faiss", "stories.faiss"),
            ("stories.faiss.map.json", "stories.faiss.map.json"),
        ]
        
        if not self.seeds_dir.exists():
            logger.debug(f"Seeds directory not found: {self.seeds_dir}")
            return
        
        for seed_name, target_name in seed_mappings:
            seed_path = self.seeds_dir / seed_name
            target_path = self.data_dir / target_name
            
            if not target_path.exists() and seed_path.exists():
                try:
                    shutil.copy2(seed_path, target_path)
                    logger.info(f"Initialized {target_name} from seed")
                except Exception as e:
                    logger.error(f"Failed to copy seed {seed_name} to {target_name}: {e}")
            elif not target_path.exists():
                logger.warning(f"No seed found for {target_name} and file doesn't exist")
        
        # Also initialize book-specific files (story_positions.json)
        self._initialize_book_seeds()
    
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
    
    def _initialize_book_seeds(self):
        """
        Initialize book-specific files from seeds.
        
        For each book, if story_positions.json is missing, copy from seeds.
        Seed path: data/seeds/books/{book_slug}/story_positions.seed.json
        """
        book_seeds_dir = self.seeds_dir / "books"
        if not book_seeds_dir.exists():
            return
        
        for book_seed_dir in book_seeds_dir.iterdir():
            if not book_seed_dir.is_dir():
                continue
            
            book_slug = book_seed_dir.name
            target_book_dir = self.books_dir / book_slug
            
            if not target_book_dir.exists():
                continue
            
            # story_positions.json
            seed_pos = book_seed_dir / "story_positions.seed.json"
            target_pos = target_book_dir / "story_positions.json"
            
            if not target_pos.exists() and seed_pos.exists():
                try:
                    shutil.copy2(seed_pos, target_pos)
                    logger.info(f"Initialized {book_slug}/story_positions.json from seed")
                except Exception as e:
                    logger.error(f"Failed to copy seed for {book_slug}/story_positions.json: {e}")
            
            # stories_meta.json
            seed_meta = book_seed_dir / "stories_meta.seed.json"
            target_meta = target_book_dir / "stories_meta.json"
            
            if not target_meta.exists() and seed_meta.exists():
                try:
                    shutil.copy2(seed_meta, target_meta)
                    logger.info(f"Initialized {book_slug}/stories_meta.json from seed")
                except Exception as e:
                    logger.error(f"Failed to copy seed for {book_slug}/stories_meta.json: {e}")


# Global singleton instance
app_state = AppState()
