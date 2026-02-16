# backend/main.py
"""
Lexicon of the Unexplained API - Main Entry Point

This file contains:
- FastAPI app initialization and CORS middleware
- Logging configuration
- Startup event (DB sync, cache warming, index cleanup)
- Health check endpoints
- Router registration

All API endpoints are organized in backend/routes/:
- routes/search.py   - Story search
- routes/tree.py     - Category tree management
- routes/stories.py  - Story CRUD operations
- routes/books.py    - Book listing and full text
- routes/admin.py    - Export, migrations, cleanup
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ------------------------------------------------------------------ #
# 1. Logging Configuration
# ------------------------------------------------------------------ #
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

log_file = os.path.join(log_dir, "backend.log")
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[file_handler, console_handler],
)
log = logging.getLogger(__name__)
log.info(f"Logging to file: {log_file} (level={LOG_LEVEL})")

# ------------------------------------------------------------------ #
# 2. Environment & Paths
# ------------------------------------------------------------------ #
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(ROOT, '.env.local'))

BOOKS_DIR = os.path.join(ROOT, "books")
DATA_DIR = os.path.join(ROOT, "data")

# ------------------------------------------------------------------ #
# 3. FastAPI App + CORS
# ------------------------------------------------------------------ #
app = FastAPI(title="Lexicon of the Unexplained API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# 4. Import and Register Routers
# ------------------------------------------------------------------ #
from fastapi import HTTPException
from routes import (
    search_router,
    tree_router,
    stories_router,
    books_router,
    admin_router,
    ai_router,
    AppError,
    app_error_handler,
    http_exception_handler,
    generic_exception_handler,
)

# Register exception handlers for consistent error responses
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
# Uncomment in production for catch-all error handling:
# app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(search_router)
app.include_router(tree_router)
app.include_router(stories_router)
app.include_router(books_router)
app.include_router(admin_router)
app.include_router(ai_router)

# ------------------------------------------------------------------ #
# 5. Import Utils (after paths defined, before startup)
# ------------------------------------------------------------------ #
from utils import (
    document_store, sync_disk_to_db, load_codex_tree,
    preload_book_metadata, rebuild_assigned_titles_cache,
    story_positions
)
from state import app_state

# ------------------------------------------------------------------ #
# 6. Category Renames (idempotent DB migration)
# ------------------------------------------------------------------ #
_CATEGORY_RENAMES = [
    ("UFO", "Extraterrestrial", None),  # top-level rename
    ("Theories Related TO THE UFO Phenomenon", "Theories Related to the Extraterrestrial Phenomenon", "Extraterrestrial"),
]

def _apply_category_renames():
    """Rename categories in the codex_nodes table. Skips if already renamed."""
    if not app_state.USE_DB or app_state.SessionLocal is None:
        return
    from models import CodexNode
    try:
        with app_state.SessionLocal() as db:
            changed = False
            for old_name, new_name, parent_name in _CATEGORY_RENAMES:
                query = db.query(CodexNode).filter_by(name=old_name)
                if parent_name:
                    parent = db.query(CodexNode).filter_by(name=parent_name).first()
                    if parent:
                        query = query.filter_by(parent_id=parent.id)
                    else:
                        continue
                node = query.first()
                if node:
                    log.info(f"Renaming category '{old_name}' → '{new_name}'")
                    node.name = new_name
                    changed = True
            if changed:
                db.commit()
                log.info("Category renames applied successfully")
    except Exception as e:
        log.error(f"Category rename migration failed: {e}", exc_info=True)

# ------------------------------------------------------------------ #
# 7. Startup Event
# ------------------------------------------------------------------ #
@app.on_event("startup")
async def startup():
    """
    Application startup tasks:
    1. Sync disk → DB (one-time heavy operation)
    2. Preload book metadata for fast search
    3. Load codex tree structure
    4. Build assigned titles cache
    5. Cleanup orphaned search index entries
    6. Warm up embedding model
    """
    from search import USE_DIRECT_SEARCH
    
    if document_store is None:
        raise RuntimeError("document_store failed to initialise")
    
    # 1. Sync disk → DB
    log.info("Performing initial disk → DB sync...")
    sync_disk_to_db()
    
    # 1b. Apply category renames (idempotent)
    _apply_category_renames()
    
    # 2. Preload book metadata
    log.info("Preloading book metadata...")
    preload_book_metadata()
    
    # 3. Load codex tree
    log.info("Loading codex tree...")
    load_codex_tree()
    
    # 4. Build assigned titles cache
    log.info("Building assigned titles cache...")
    rebuild_assigned_titles_cache()
    
    # 5. Cleanup orphaned search entries
    log.info("Cleaning up orphaned search index entries...")
    valid_titles = set()
    for book_slug, positions in story_positions.items():
        valid_titles.update(positions.keys())
    log.info(f"Valid titles from disk: {len(valid_titles)}")
    
    if USE_DIRECT_SEARCH:
        from search.engine import get_search_engine
        engine = get_search_engine()
        deleted_count, deleted_titles = engine.cleanup_orphaned_entries(valid_titles)
        if deleted_count > 0:
            log.info(f"Removed {deleted_count} orphaned entries from search index: {deleted_titles}")
    else:
        # Legacy Haystack cleanup
        try:
            import numpy as np
            from utils import document_store_path
            all_docs = list(document_store.filter_documents({}))
            orphaned_ids = []
            orphaned_titles = []
            for doc in all_docs:
                title = doc.meta.get("title") if doc.meta else None
                if title and title not in valid_titles:
                    orphaned_ids.append(doc.id)
                    if title not in orphaned_titles:
                        orphaned_titles.append(title)
            if orphaned_ids:
                document_store.delete_documents(orphaned_ids)
                remaining_docs = list(document_store.filter_documents({}))
                for doc in remaining_docs:
                    if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                        doc.embedding = doc.embedding.tolist()
                document_store.save_to_disk(document_store_path)
                log.info(f"Removed {len(orphaned_ids)} orphaned documents from Haystack: {orphaned_titles}")
        except Exception as e:
            log.warning(f"Failed to cleanup Haystack orphaned entries: {e}")
    
    # 6. Auto-rebuild search index if new stories are missing
    #    The rebuild is DEFERRED to a background thread so the server can
    #    bind its port immediately and satisfy Render's health-check timeout.
    _rebuilding_in_background = False
    if USE_DIRECT_SEARCH:
        from search.engine import get_search_engine
        engine = get_search_engine()
        indexed_titles = {
            m.get("title")
            for m in engine.faiss_index.metadata.values()
            if m and m.get("title")
        }
        dict_titles = set(app_state.stories_dict.keys())
        missing = dict_titles - indexed_titles
        if missing:
            log.info(
                f"Search index is missing {len(missing)} stories – "
                f"scheduling background rebuild. Sample: {list(missing)[:5]}"
            )
            import asyncio, concurrent.futures
            _rebuild_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            def _background_rebuild():
                try:
                    from search.engine_compat import rebuild_search_index
                    rebuild_search_index()
                    log.info("Background search index rebuild complete")
                except Exception as e:
                    log.error(f"Background search index rebuild failed: {e}", exc_info=True)

            asyncio.get_event_loop().run_in_executor(_rebuild_executor, _background_rebuild)
            _rebuilding_in_background = True
        else:
            log.info(
                f"Search index up-to-date: {len(indexed_titles)} indexed, "
                f"{len(dict_titles)} in stories_dict"
            )
    
    # 7. Warm up embedding model (skip if rebuild is running – it loads the model itself)
    if USE_DIRECT_SEARCH and not _rebuilding_in_background:
        log.info("Warming up embedding model...")
        engine.warm_up()
        test_results = engine.search("warmup query", top_k=1)
        log.info(f"Direct search engine warmed up (test returned {len(test_results)} results)")
    elif not USE_DIRECT_SEARCH:
        log.info("Warming up embedding model...")
        from utils import both_pipeline
        dummy_results = both_pipeline.run({
            "embedder": {"text": "warmup query"},
            "retriever_embedding": {"top_k": 1, "filters": None},
            "retriever_bm25": {"query": "warmup query", "top_k": 1, "filters": None}
        })
        log.info("Haystack embedding model warmed up")
    
    log.info("API ready – docs:%s", document_store.count_documents())

# ------------------------------------------------------------------ #
# 7. Health Check Endpoints
# ------------------------------------------------------------------ #
@app.get("/")
def root():
    """Root endpoint for health checks."""
    return {"status": "API is running", "docs": "/docs"}


@app.get("/api/health")
def health():
    """Detailed health check with stats."""
    books = len([d for d in os.listdir(BOOKS_DIR)
                 if os.path.isdir(os.path.join(BOOKS_DIR, d)) and not d.startswith(".")])
    return {
        "status": "OK",
        "books_found": books,
        "documents_loaded": document_store.count_documents(),
    }

# ------------------------------------------------------------------ #
# 8. Run with Uvicorn (development)
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
