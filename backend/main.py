# backend/main.py
import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import jwt
from jwt import PyJWKClient  # Added import for PyJWKClient
from dotenv import load_dotenv
from sqlalchemy.orm import Session  # Added for DB session
from models import SessionLocal, User  # Assuming models.py has SessionLocal (engine session maker) and User model
import urllib.parse  # Add this line
import json
import requests
from datetime import datetime

# ------------------------------------------------------------------ #
# 1. Logging
# ------------------------------------------------------------------ #
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

# Read log level from environment (default INFO for production)
# Set LOG_LEVEL=DEBUG for verbose logging during development
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

# Set up rotating file handler (10MB max, keep 5 backups)
log_file = os.path.join(log_dir, "backend.log")
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

# Console always shows INFO+ (less noisy for terminal)
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
# 2. FastAPI app + CORS
# ------------------------------------------------------------------ #
app = FastAPI(title="Lexicon of the Unexplained API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------------------------------------------ #
# 3. Load environment variables
# ------------------------------------------------------------------ #
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(ROOT, '.env.local'))
# ------------------------------------------------------------------ #
# 4. Paths (relative to repo root)
# ------------------------------------------------------------------ #
BOOKS_DIR = os.path.join(ROOT, "books")
DATA_DIR = os.path.join(ROOT, "data")
# ------------------------------------------------------------------ #
# 5. Import utils **after** paths are defined
# ------------------------------------------------------------------ #
from utils import (
    document_store, both_pipeline, keyword_pipeline, semantic_pipeline,
    search_stories, load_codex_tree, save_codex_tree, sync_disk_to_db, get_cached_tree, invalidate_cache,
    preload_book_metadata, clear_book_metadata_cache,
    assign_to_path, remove_from_path,
    render_md_with_scroll_and_highlight, render_static_story,
    export_stories, get_stories_at_path, find_paths_for_title,
    load_story_positions, update_story_boundaries, update_story_title, sources, # needed for render fallback
    rebuild_assigned_titles_cache,  # Add this import
    engine,  # Add this for migration
)
# ------------------------------------------------------------------ #
# 6. Startup – sanity check
# ------------------------------------------------------------------ #
@app.on_event("startup")
async def startup():
    from search import USE_DIRECT_SEARCH
    
    if document_store is None:
        raise RuntimeError("document_store failed to initialise")
    
    # ONE-TIME heavy operation: Sync disk → DB
    log.info("Performing initial disk → DB sync...")
    sync_disk_to_db()
    
    # Preload book metadata to avoid DB queries during search
    log.info("Preloading book metadata...")
    preload_book_metadata()
    
    # Initial tree load (now lightweight)
    log.info("Loading codex tree...")
    load_codex_tree()
    
    # Initialize assigned titles cache
    log.info("Building assigned titles cache...")
    rebuild_assigned_titles_cache()  # Add this line
    
    # Cleanup orphaned entries from search index (stories deleted from disk but still in index)
    log.info("Cleaning up orphaned search index entries...")
    from utils import story_positions
    valid_titles = set()
    for book_slug, positions in story_positions.items():
        valid_titles.update(positions.keys())
    log.info(f"Valid titles from disk: {len(valid_titles)}")
    
    if USE_DIRECT_SEARCH:
        # Direct engine cleanup
        from search.engine import get_search_engine
        engine = get_search_engine()
        deleted_count, deleted_titles = engine.cleanup_orphaned_entries(valid_titles)
        if deleted_count > 0:
            log.info(f"Removed {deleted_count} orphaned entries from search index: {deleted_titles}")
    else:
        # Legacy Haystack cleanup (manual)
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
                # Save updated document store
                remaining_docs = list(document_store.filter_documents({}))
                for doc in remaining_docs:
                    if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                        doc.embedding = doc.embedding.tolist()
                document_store.save_to_disk(document_store_path)
                log.info(f"Removed {len(orphaned_ids)} orphaned documents from Haystack: {orphaned_titles}")
        except Exception as e:
            log.warning(f"Failed to cleanup Haystack orphaned entries: {e}")
    
    # Warm-up embedding model
    log.info("Warming up embedding model...")
    
    if USE_DIRECT_SEARCH:
        # Direct engine warm-up
        from search.engine import get_search_engine
        engine = get_search_engine()
        engine.warm_up()
        # Test search
        test_results = engine.search("warmup query", top_k=1)
        log.info(f"Direct search engine warmed up (test returned {len(test_results)} results)")
    else:
        # Legacy Haystack warm-up
        dummy_results = both_pipeline.run({
            "embedder": {"text": "warmup query"},
            "retriever_embedding": {"top_k": 1, "filters": None},
            "retriever_bm25": {"query": "warmup query", "top_k": 1, "filters": None}
        })
        log.info("Haystack embedding model warmed up")
    
    log.info("API ready – docs:%s", document_store.count_documents())
# ------------------------------------------------------------------ #
# Auth Middleware
# ------------------------------------------------------------------ #
# Allow bypassing auth in development (set DISABLE_AUTH=true in .env.local)
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"
security = HTTPBearer(auto_error=False) # Don't auto-error, we'll handle it

# Use project-specific JWKS URL from env (should match frontend VITE_STACK_PROJECT_ID)
STACK_PROJECT_ID = os.getenv("STACK_PROJECT_ID") or os.getenv("VITE_STACK_PROJECT_ID") or os.getenv("NEXT_PUBLIC_STACK_PROJECT_ID")
STACK_JWKS_URL = os.getenv("STACK_JWKS_URL")  # Optional explicit override from Stack dashboard

JWKS_URL = None
jwks_client = None

if not STACK_PROJECT_ID and not STACK_JWKS_URL:
    log.warning("STACK_PROJECT_ID / STACK_JWKS_URL not found in environment variables. JWT verification will fail.")
else:
    # Prefer explicit JWKS URL if provided in env
    if STACK_JWKS_URL:
        JWKS_URL = STACK_JWKS_URL
    elif STACK_PROJECT_ID:
        # Try the common paths, prefer /.well-known/jwks.json then fallback to /.well-known
        JWKS_URL = f"https://api.stack-auth.com/api/v1/projects/{STACK_PROJECT_ID}/.well-known/jwks.json"
    try:
        if JWKS_URL:
            log.info(f"Using JWKS URL: {JWKS_URL}")
            jwks_client = PyJWKClient(JWKS_URL)
            try:
                resp = requests.get(JWKS_URL, timeout=5)
                resp.raise_for_status()
                jwks_data = resp.json()
                kids = [key.get("kid") for key in jwks_data.get("keys", [])]
                log.info(f"JWKS contains keys: {kids}")
            except Exception as jwks_fetch_err:
                log.warning(f"Failed to fetch JWKS keys for logging: {jwks_fetch_err}")
    except Exception as e:
        log.error(f"Failed to initialize JWKS client with URL '{JWKS_URL}': {e}")
        jwks_client = None

SECRET_SERVER_KEY = os.getenv("STACK_SECRET_SERVER_KEY")
EDITOR_EMAILS = {e.strip().lower() for e in os.getenv("EDITOR_EMAILS", "").split(",") if e.strip()}

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    # If auth is disabled for development, return a mock user
    if DISABLE_AUTH:
        return {"sub": "dev-user"}  # Role will be checked separately
    
    # Try to get token from Authorization header first
    token = None
    if credentials:
        token = credentials.credentials
    
    # If no token in header, try to get from cookies (for Stack Auth cookie storage)
    if not token:
        # Check for common Stack Auth cookie names
        # Preferred: Stack 'stack-access' cookie which is a JSON-encoded array [refresh_id, access_jwt]
        stack_access_raw = request.cookies.get('stack-access')
        if stack_access_raw:
            try:
                decoded = urllib.parse.unquote(stack_access_raw)
                parsed = json.loads(decoded)
                if isinstance(parsed, list) and len(parsed) >= 2 and isinstance(parsed[1], str):
                    token = parsed[1]
                    log.debug("Using JWT from 'stack-access' cookie")
            except Exception as e:
                log.warning(f"Failed to parse 'stack-access' cookie: {e}")

        # Other common names if not found
        if not token:
            token = request.cookies.get('stack-access-token') or \
                   request.cookies.get('stack_token') or \
                   request.cookies.get('__session') or \
                   request.cookies.get('session') or \
                   (request.cookies.get(f'stack-{STACK_PROJECT_ID}-access-token') if STACK_PROJECT_ID else None)

        # Fallback: scan cookies for any JWT-looking value if still not found
        if not token and request.cookies:
            for cookie_name, cookie_val in request.cookies.items():
                # Heuristic: JWT has two dots and is reasonably long
                if isinstance(cookie_val, str) and cookie_val.count('.') == 2 and len(cookie_val) > 100:
                    token = cookie_val
                    log.debug(f"Using JWT from cookie '{cookie_name}'")
                    break
    
    if not token:
        raise HTTPException(401, "Authentication required")
    
    if not jwks_client:
        raise HTTPException(500, "JWT verification not configured. Set STACK_PROJECT_ID in environment.")
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        # Stack Auth tokens might use different audience/issuer - try both with and without audience verification
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=SECRET_SERVER_KEY if SECRET_SERVER_KEY else None,
                options={"verify_exp": True, "verify_aud": bool(SECRET_SERVER_KEY)}
            )
        except jwt.InvalidAudienceError:
            # If audience verification fails, try without it (Stack Auth might not use audience)
            log.warning("Token audience verification failed, trying without audience check")
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_exp": True, "verify_aud": False}
            )
        log.debug(f"Successfully decoded JWT for user: {payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token has expired")
    except Exception as e:
        log.error(f"JWT verification failed: {str(e)}")
        raise HTTPException(401, f"Invalid token: {str(e)}")

async def require_editor(user: Dict = Depends(get_current_user)):
    if DISABLE_AUTH:
        return user  # Skip role check in dev
    
    # Auto-provision user and enforce role
    session = SessionLocal()
    try:
        sub = user.get("sub")
        email = (user.get("email") or "").lower()
        name = user.get("name") or ""
        
        log.info(f"require_editor: checking user sub={sub}, email={email}, name={name}")
        log.info(f"require_editor: EDITOR_EMAILS={EDITOR_EMAILS}, email in list={email in EDITOR_EMAILS}")

        db_user = session.query(User).filter_by(id=sub).first()

        # Auto-provision if missing
        if not db_user:
            db_user = User(id=sub, name=name, email=email, role="viewer")
            session.add(db_user)
            session.commit()
            log.info(f"Auto-provisioned user {email or sub} with role 'viewer'")

        # Auto-promote to editor if email matches allowlist
        if email and email in EDITOR_EMAILS and db_user.role != "editor":
            db_user.role = "editor"
            session.commit()
            log.info(f"Auto-promoted {email} to 'editor' via EDITOR_EMAILS")
        
        log.info(f"require_editor: db_user.role={db_user.role if db_user else None}, required=editor")

        if not db_user or db_user.role != "editor":
            log.warning(f"Access denied: user {email or sub} has role '{db_user.role if db_user else None}', needs 'editor'")
            raise HTTPException(403, "Editor role required")
        return user
    finally:
        session.close()

# ------------------------------------------------------------------ #
# 7. Pydantic models (pattern instead of regex)
# ------------------------------------------------------------------ #
class SearchQuery(BaseModel):
    query: str
    source_filter: Optional[str] = "All Sources"
    type_filter: Optional[str] = "Both"
    search_mode: Optional[str] = "Both"
    top_k: int = Field(1000, ge=1, le=5000)
    min_score: float = Field(0.1, ge=0.0, le=1.0)
    assignment_filter: Optional[str] = "all"
class AssignBody(BaseModel):
    path: List[str] # e.g. ["Demonic Activity","Obsession","Fear/Anxiety"]
    story: Dict[str, Any]
class RemoveBody(BaseModel):
    path: List[str]
    title: str
class ExportBody(BaseModel):
    stories: List[Dict[str, Any]]
    format: str = Field("md", pattern="^(md|pdf|word)$") # fixed
    is_single: bool = True
class RenderQuery(BaseModel):
    title: str
    mode: str = Field("static", pattern="^(static|book)$")
    search_query: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
class UpdateBoundariesBody(BaseModel):
    title: str
    book_slug: str
    start_char: int
    end_char: int
class UpdateTitleBody(BaseModel):
    old_title: str
    new_title: str
    book_slug: str

class AddStoryBody(BaseModel):
    book_slug: str
    title: str
    start_char: int
    end_char: int
    pages: str
    keywords: str = ""
    force_overlap: bool = False

class ReindexResponse(BaseModel):
    status: str
    indexed_count: int
    duration_seconds: float
    errors: List[str] = []

class BookResponse(BaseModel):
    id: int
    slug: str
    title: str
    author: Optional[str]
    year: Optional[str]
    story_count: Optional[int] = 0

    class Config:
        from_attributes = True

# ------------------------------------------------------------------ #
# 8. End-points
# ------------------------------------------------------------------ #
@app.get("/")
def root():
    """Simple root endpoint to handle health checks and reduce 404 noise."""
    return {"status": "API is running", "docs": "/docs"}

@app.get("/api/health")
def health():
    books = len([d for d in os.listdir(BOOKS_DIR)
                 if os.path.isdir(os.path.join(BOOKS_DIR, d)) and not d.startswith(".")])
    return {
        "status": "OK",
        "books_found": books,
        "documents_loaded": document_store.count_documents(),
    }
# ------------------- SEARCH ------------------- #
@app.post("/api/search")
def api_search(body: SearchQuery):
    try:
        results = search_stories(
            query=body.query,
            source_filter=body.source_filter,
            type_filter=body.type_filter,
            search_mode=body.search_mode,
            top_k=body.top_k,
            min_score=body.min_score,
            assignment_filter=body.assignment_filter,  # Add this line
        )
        return {"results": results}
    except Exception as e:
        log.error(f"Search failed: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Search failed: {str(e)}")
# ------------------- TREE ------------------- #
@app.get("/api/get-tree")
def get_tree():
    return get_cached_tree()
# ------------------- SOURCES ------------------- #
@app.get("/api/sources")
def get_sources():
    return {"sources": sources}

# ------------------- BOOKS ------------------- #
@app.get("/api/books", response_model=List[BookResponse])
def get_books():
    """Get all books with story counts"""
    from models import Book
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

@app.get("/api/books/{slug}")
def get_book(slug: str, include_stories: bool = False):
    """Get a single book by slug, optionally with its stories"""
    from models import Book
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

# ------------------- FULL TEXT ------------------- #
@app.get("/api/full-text/{book_slug}")
def get_full_text(book_slug: str):
    from utils import load_full_md
    try:
        full_text = load_full_md(book_slug)
        return {"text": full_text, "length": len(full_text)}
    except Exception as e:
        raise HTTPException(404, f"Book not found: {book_slug}")
@app.get("/api/get-stories/{path:path}")
def get_stories(path: str, subcats: Optional[str] = None):
    log.debug(f"Raw path received: {repr(path)}")
    parts = [urllib.parse.unquote(p.strip()) for p in path.split("/") if p.strip()]
    log.debug(f"After split and decode: {parts}")
    tree = get_cached_tree()
    log.debug(f"Getting stories for path: {parts}")
    log.debug(f"Tree structure at root: {list(tree.keys())[:5]}...")  # First 5 keys
    
    if subcats:
        from tree.queries import get_stories_for_subcats
        from utils import stories_dict, enrich_stories_with_book_metadata
        subcat_list = [s.strip() for s in subcats.split(",") if s.strip()]
        log.debug(f"Filtering by subcategories: {subcat_list}")
        # get_stories_for_subcats returns just titles, need to resolve to full objects
        titles = get_stories_for_subcats(tree, parts, subcat_list)
        stories = [stories_dict[title] for title in titles if title in stories_dict]
        stories = enrich_stories_with_book_metadata(stories)
    else:
        stories = get_stories_at_path(tree, parts)
    log.debug(f"Found {len(stories)} stories for path {parts}")
    if len(stories) == 0 and len(parts) > 0:
        # Debug: check what we find at each level
        current = tree
        for i, part in enumerate(parts):
            log.debug(f"Level {i}: looking for '{part}' in {list(current.keys()) if isinstance(current, dict) else type(current)}")
            if part in current:
                current = current[part]
                log.debug(f"Found '{part}', continuing...")
            else:
                log.debug(f"'{part}' not found, stopping")
                break
        log.debug(f"Final current: {current}")
    return stories
@app.get("/api/get-unassigned")
def get_unassigned():
    from utils import stories_dict, enrich_stories_with_book_metadata
    from utils.cache import get_assigned_titles_set
    assigned = get_assigned_titles_set()
    unassigned = [s for t, s in stories_dict.items() if t not in assigned]
    return enrich_stories_with_book_metadata(unassigned)
@app.post("/api/assign-category")
def assign_category(body: AssignBody, user: Dict = Depends(require_editor)):
    from utils import stories_dict, USE_DB, SessionLocal
    from models import Story, CodexNode, NodeStory
    
    # Ensure story exists in database if using DB
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            existing_story = db.query(Story).filter_by(title=body.story['title']).first()
            if not existing_story:
                # Create story in database
                db.add(Story(**body.story))
                db.commit()
                log.info(f"Created story {body.story['title']} in database")
            
            # Directly assign to database node (more reliable than rebuilding entire tree)
            # Navigate to the target node
            current_parent_id = None
            target_node = None
            
            for level_name in body.path:
                query = db.query(CodexNode).filter_by(name=level_name)
                if current_parent_id:
                    query = query.filter_by(parent_id=current_parent_id)
                else:
                    query = query.filter_by(parent_id=None)
                target_node = query.first()
                
                if not target_node:
                    # Create node if it doesn't exist
                    target_node = CodexNode(name=level_name, parent_id=current_parent_id)
                    db.add(target_node)
                    db.flush()
                    log.info(f"Created node '{level_name}' in database")
                
                current_parent_id = target_node.id
            
            if target_node:
                # Get the story
                story = db.query(Story).filter_by(title=body.story['title']).first()
                if story:
                    # Check if relationship already exists
                    existing = db.query(NodeStory).filter_by(
                        node_id=target_node.id, story_id=story.id
                    ).first()
                    if not existing:
                        db.add(NodeStory(node_id=target_node.id, story_id=story.id))
                        db.commit()
                        log.info(f"Directly assigned story '{body.story['title']}' to node '{target_node.name}' (id={target_node.id})")
                    else:
                        log.info(f"Story '{body.story['title']}' already assigned to node '{target_node.name}'")
                else:
                    log.warning(f"Story '{body.story['title']}' not found in database")
            else:
                log.error(f"Could not find or create target node for path: {body.path}")
    
    # Also update the in-memory tree and JSON for consistency (like original app.py)
    # But don't sync back to database - that's already done above
    from utils import assign_to_path, save_codex_tree_to_json, stories_dict, stories_dict_path, codex_tree_path
    import json
    
    tree = get_cached_tree()
    updated = assign_to_path(tree, body.path, body.story)
    # Save to JSON only (like original app.py) - database is already updated via direct assignment
    save_codex_tree_to_json(updated)
    if stories_dict:
        with open(stories_dict_path, "w") as f:
            json.dump(stories_dict, f, indent=4, sort_keys=True)
    
    # Invalidate cache since we changed the tree
    invalidate_cache()
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_change
        on_category_change("Assign", body.story['title'], body.path)
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")
    
    return {"status": "assigned"}
@app.delete("/api/remove-category")
def remove_category(body: RemoveBody, user: Dict = Depends(require_editor)):
    from utils import USE_DB, SessionLocal
    from models import Story, CodexNode, NodeStory
    
    # Remove from database if available
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            # Navigate to the target node
            current_parent_id = None
            target_node = None
            
            for level_name in body.path:
                query = db.query(CodexNode).filter_by(name=level_name)
                if current_parent_id:
                    query = query.filter_by(parent_id=current_parent_id)
                else:
                    query = query.filter_by(parent_id=None)
                target_node = query.first()
                
                if not target_node:
                    log.warning(f"Node '{level_name}' not found in database for path: {body.path}")
                    break
                
                current_parent_id = target_node.id
            
            if target_node:
                # Get the story
                story = db.query(Story).filter_by(title=body.title).first()
                if story:
                    # Remove the relationship
                    node_story = db.query(NodeStory).filter_by(
                        node_id=target_node.id, story_id=story.id
                    ).first()
                    if node_story:
                        db.delete(node_story)
                        db.commit()
                        log.info(f"Removed story '{body.title}' from node '{target_node.name}' (node_id={target_node.id})")
                    else:
                        log.warning(f"Story '{body.title}' not assigned to node '{target_node.name}'")
                else:
                    log.warning(f"Story '{body.title}' not found in database")
            else:
                log.error(f"Could not find target node for path: {body.path}")
    
    # Also update the in-memory tree and JSON for consistency
    from utils import remove_from_path, save_codex_tree_to_json
    tree = get_cached_tree()
    updated = remove_from_path(tree, body.path, body.title)
    save_codex_tree_to_json(updated)
    
    # Invalidate cache since we changed the tree
    invalidate_cache()
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_change
        on_category_change("Remove", body.title, body.path)
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")
    
    return {"status": "removed"}
# ------------------- RENDER ------------------- #
@app.post("/api/render-story")
def render_story(body: RenderQuery):
    from utils import stories_dict, find_book_slug, USE_DB, SessionLocal
    story = stories_dict.get(body.title)
    if not story:
        # fallback: search by title across all books
        try:
            book_slug = find_book_slug(body.title)
            positions = load_story_positions(book_slug)
            pos = positions[body.title]
            story = {
                "title": body.title,
                "book_slug": book_slug,
                "pages": pos.get("pages", ""),
                "keywords": ", ".join(pos.get("keywords", [])),
                "start_char": pos.get("start_char", 0),
                "end_char": pos.get("end_char", 0),
            }
        except Exception:
            # Final fallback: check the database in case the story was renamed
            # and stories_dict hasn't been reloaded yet
            if USE_DB and SessionLocal:
                try:
                    from models import Story
                    with SessionLocal() as db:
                        db_story = db.query(Story).filter_by(title=body.title).first()
                        if db_story:
                            story = {
                                "title": db_story.title,
                                "book_slug": db_story.book_slug,
                                "pages": db_story.pages or "",
                                "keywords": db_story.keywords or "",
                                "start_char": db_story.start_char or 0,
                                "end_char": db_story.end_char or 0,
                            }
                        else:
                            raise HTTPException(404, "Story not found")
                except Exception as e:
                    log.error(f"Error querying database for story '{body.title}': {e}")
                    raise HTTPException(404, "Story not found")
            else:
                raise HTTPException(404, "Story not found")
    
    # Use provided boundaries if available, otherwise use story boundaries
    start_char = body.start_char if body.start_char is not None else story["start_char"]
    end_char = body.end_char if body.end_char is not None else story["end_char"]
    
    if body.mode == "static":
        # Create a modified story dict with updated boundaries
        modified_story = {**story, "start_char": start_char, "end_char": end_char}
        return {"html": render_static_story(modified_story)}
    else: # book mode
        html = render_md_with_scroll_and_highlight(
            book_slug=story["book_slug"],
            start_char=start_char,
            end_char=end_char,
            page=story["pages"].split("-")[0],
            search_query=body.search_query,
        )
        return {"html": html}
# ------------------- UPDATE BOUNDARIES ------------------- #
@app.post("/api/update-boundaries")
def update_boundaries(body: UpdateBoundariesBody, user = Depends(require_editor)):
    success = update_story_boundaries(
        book_slug=body.book_slug,
        title=body.title,
        start_char=body.start_char,
        end_char=body.end_char
    )
    if success:
        return {"status": "updated", "message": f"Boundaries updated for {body.title}"}
    else:
        raise HTTPException(400, "Failed to update boundaries")
# ------------------- UPDATE TITLE ------------------- #
@app.post("/api/update-title")
def update_title(body: UpdateTitleBody, user = Depends(require_editor)):
    success = update_story_title(
        book_slug=body.book_slug,
        old_title=body.old_title,
        new_title=body.new_title
    )
    if success:
        return {"status": "updated", "message": f"Title updated from '{body.old_title}' to '{body.new_title}'"}
    else:
        raise HTTPException(400, "Failed to update title")
# ------------------- ADD STORY (IMMEDIATE INDEXING) ------------------- #
@app.post("/api/add-story")
def add_story(body: AddStoryBody, user = Depends(require_editor)):
    """
    Add a new story to a book and immediately index it for search.
    Story is searchable as soon as this endpoint returns.
    """
    try:
        # 1. Validate book exists
        book_path = os.path.join(BOOKS_DIR, body.book_slug)
        if not os.path.isdir(book_path):
            raise HTTPException(404, f"Book not found: {body.book_slug}")
        
        # 2. Load full text to validate positions
        from utils import load_full_md
        full_md = load_full_md(body.book_slug)
        if not full_md:
            raise HTTPException(404, f"Full_Text.md not found for {body.book_slug}")
        
        # 3. Validate positions
        if body.start_char < 0 or body.end_char > len(full_md):
            raise HTTPException(400, f"Character positions out of bounds (0-{len(full_md)})")
        
        if body.end_char <= body.start_char:
            raise HTTPException(400, "end_char must be greater than start_char")
        
        # 4. Extract and validate story text
        story_text = full_md[body.start_char:body.end_char].strip()
        if not story_text:
            raise HTTPException(400, "Story text is empty")
        
        if len(story_text) < 50:
            raise HTTPException(400, f"Story too short ({len(story_text)} chars). Minimum 50 characters.")
        
        # 5. Check for duplicate title
        from utils import load_story_positions
        positions = load_story_positions(body.book_slug)
        if body.title in positions:
            raise HTTPException(400, f"Story title '{body.title}' already exists in {body.book_slug}")
        
        # 6. Check for overlaps
        from utils import check_story_overlap
        has_overlap, overlaps = check_story_overlap(body.book_slug, body.start_char, body.end_char)
        
        log.info(f"Overlap check: has_overlap={has_overlap}, force_overlap={body.force_overlap}, overlaps={len(overlaps) if has_overlap else 0}")
        
        if has_overlap and not body.force_overlap:
            # Return overlap warning, require confirmation
            log.info(f"Returning overlap warning for '{body.title}': {overlaps}")
            return {
                "status": "overlap_warning",
                "message": "Story overlaps with existing stories",
                "overlaps": overlaps,
                "requires_confirmation": True
            }
        
        # 7. Parse keywords
        keywords_list = [k.strip() for k in body.keywords.split(",") if k.strip()]
        
        # 8. Update story_positions.json
        positions[body.title] = {
            "start_char": body.start_char,
            "end_char": body.end_char,
            "pages": body.pages,
            "keywords": keywords_list
        }
        from utils import story_positions, save_story_positions
        story_positions[body.book_slug] = positions
        save_success = save_story_positions(body.book_slug)
        
        if not save_success:
            raise HTTPException(500, "Failed to save story_positions.json")
        
        log.info(f"Saved story '{body.title}' to story_positions.json")
        
        # 9. Add to database (if enabled)
        from utils import USE_DB, SessionLocal
        if USE_DB and SessionLocal:
            try:
                with SessionLocal() as db:
                    from models import Story, Book
                    
                    book = db.query(Book).filter_by(slug=body.book_slug).first()
                    if book:
                        story = Story(
                            title=body.title,
                            book_id=book.id,
                            book_slug=body.book_slug,
                            pages=body.pages,
                            keywords=",".join(keywords_list),
                            start_char=body.start_char,
                            end_char=body.end_char
                        )
                        db.add(story)
                        db.commit()
                        log.info(f"Added story '{body.title}' to database")
            except Exception as e:
                log.error(f"Failed to add story to database: {e}")
                # Don't fail the entire operation if DB fails
        
        # 10. IMMEDIATE INDEXING: Embed the story right now
        log.info(f"Embedding story '{body.title}' immediately...")
        from search import USE_DIRECT_SEARCH
        import numpy as np
        
        if USE_DIRECT_SEARCH:
            # Direct FAISS + SQLite engine
            from search.engine import get_search_engine
            from search.models import StoryDocument
            
            engine = get_search_engine()
            
            # Create StoryDocument
            doc_id = f"{body.book_slug}_{hash(body.title) & 0xFFFFFFFF}"
            story_doc = StoryDocument(
                id=doc_id,
                content=story_text,
                meta={
                    "type": "story",
                    "title": body.title,
                    "book": body.book_slug,
                    "source": body.book_slug.replace('_', ' '),
                    "pages": body.pages,
                    "keywords": ", ".join(keywords_list),
                    "start_char": body.start_char,
                    "end_char": body.end_char
                },
                embedding=None  # Will be generated by engine
            )
            
            # Add to engine (handles embedding + FAISS + FTS5)
            engine.add_document(story_doc)
            engine.save()
            
            log.info(f"Story '{body.title}' embedded and added to Direct search engine")
        else:
            # Legacy Haystack
            from haystack import Document
            from utils import embedder_doc, document_store, document_store_path
            
            story_doc = Document(
                content=story_text,
                meta={
                    "type": "story",
                    "title": body.title,
                    "book": body.book_slug,
                    "source": body.book_slug.replace('_', ' '),
                    "pages": body.pages,
                    "keywords": ", ".join(keywords_list),
                    "start_char": body.start_char,
                    "end_char": body.end_char
                }
            )
            
            # Embed the story
            result = embedder_doc.run([story_doc])
            embedded_doc = result["documents"][0]
            
            # Convert embedding to list for JSON serialization
            if embedded_doc.embedding is not None and isinstance(embedded_doc.embedding, np.ndarray):
                embedded_doc.embedding = embedded_doc.embedding.tolist()
            
            # Add to document store
            document_store.write_documents([embedded_doc])
            
            # Convert ALL embeddings to lists before saving
            all_docs = list(document_store.filter_documents({}))
            for doc in all_docs:
                if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                    doc.embedding = doc.embedding.tolist()
            
            document_store.save_to_disk(document_store_path)
            
            log.info(f"Story '{body.title}' embedded and added to Haystack document store")
        
        # 11. Update stories_dict cache
        from utils import stories_dict
        stories_dict[body.title] = {
            "title": body.title,
            "book_slug": body.book_slug,
            "pages": body.pages,
            "keywords": ", ".join(keywords_list),
            "start_char": body.start_char,
            "end_char": body.end_char
        }
        log.info(f"Updated stories_dict cache with '{body.title}'")
        
        # 12. Invalidate cache
        from utils import invalidate_cache
        invalidate_cache()
        
        # 13. Auto-sync to GitHub
        try:
            from sync.github_sync import on_story_added
            on_story_added(body.book_slug, body.title)
        except Exception as e:
            log.debug(f"GitHub sync skipped: {e}")
        
        log.info(f"Story '{body.title}' added to {body.book_slug} by {user.get('email')} and is now searchable!")
        
        return {
            "status": "success",
            "message": f"Story '{body.title}' saved and indexed successfully. It is now searchable!",
            "story": {
                "title": body.title,
                "book_slug": body.book_slug,
                "pages": body.pages,
                "start_char": body.start_char,
                "end_char": body.end_char,
                "length": len(story_text),
                "indexed": True
            },
            "overlap_warnings": [f"{o['title']} ({o['overlap_percent']}% overlap)" for o in overlaps] if has_overlap else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to add story: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to add story: {str(e)}")

# ------------------- DELETE STORY ------------------- #
@app.delete("/api/delete-story/{title}")
def delete_story(title: str, user = Depends(require_editor)):
    """
    Delete a story from story_positions.json, database, and document store.
    Also removes it from the codex tree and pending queue if present.
    """
    try:
        from utils import stories_dict, story_positions, save_story_positions, load_pending_stories, save_pending_stories
        
        log.info(f"Deleting story '{title}' requested by {user.get('email')}")
        
        # 1. Find which book this story belongs to
        book_slug = None
        for slug, positions in story_positions.items():
            if title in positions:
                book_slug = slug
                break
        
        if not book_slug:
            raise HTTPException(404, f"Story '{title}' not found in any book")
        
        # 2. Remove from story_positions.json
        from utils import load_story_positions
        positions = load_story_positions(book_slug)
        if title in positions:
            del positions[title]
            story_positions[book_slug] = positions
            save_story_positions(book_slug)
            log.info(f"Removed '{title}' from story_positions.json for {book_slug}")
        
        # 3. Remove from stories_dict cache
        if title in stories_dict:
            del stories_dict[title]
        
        # 4. Remove from database (if enabled)
        from utils import USE_DB, SessionLocal as UtilsSessionLocal
        if USE_DB and UtilsSessionLocal:
            try:
                with UtilsSessionLocal() as db:
                    from models import Story
                    
                    # Delete story (cascade will handle NodeStory relationships)
                    story = db.query(Story).filter_by(title=title).first()
                    if story:
                        db.delete(story)
                        db.commit()
                        log.info(f"Deleted story '{title}' from database")
                    else:
                        log.warning(f"Story '{title}' not found in database to delete")
            except Exception as e:
                log.error(f"Failed to delete from database: {e}")
        
        # 5. Remove from document store / search engine
        from search import USE_DIRECT_SEARCH
        
        if USE_DIRECT_SEARCH:
            # Direct FAISS + SQLite engine
            try:
                from search.engine import get_search_engine
                engine = get_search_engine()
                
                # Delete by title from both FAISS and FTS indices
                deleted = engine.delete_by_title(title)
                if deleted:
                    log.info(f"Removed '{title}' from Direct search engine ({deleted} entries)")
                else:
                    log.warning(f"'{title}' not found in Direct search engine")
                
                engine.save()
            except Exception as e:
                log.error(f"Failed to remove from Direct search engine: {e}")
                # Don't fail the entire operation
        else:
            # Legacy Haystack
            try:
                from utils import document_store, document_store_path
                import numpy as np
                
                # Find document by title in meta
                docs = document_store.filter_documents({"field": "meta.title", "operator": "==", "value": title})
                if docs:
                    doc_ids = [doc.id for doc in docs]
                    document_store.delete_documents(doc_ids)
                    
                    # Convert all embeddings to lists before saving
                    all_docs = list(document_store.filter_documents({}))
                    docs_to_update = []
                    for doc in all_docs:
                        if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                            doc.embedding = doc.embedding.tolist()
                            docs_to_update.append(doc)
                    
                    if docs_to_update:
                        document_store.delete_documents([doc.id for doc in docs_to_update])
                        document_store.write_documents(docs_to_update)
                    
                    document_store.save_to_disk(document_store_path)
                    log.info(f"Removed '{title}' from Haystack document store ({len(doc_ids)} documents)")
            except Exception as e:
                log.error(f"Failed to remove from Haystack document store: {e}")
                # Don't fail the entire operation
        
        # 6. Remove from codex tree (if assigned)
        try:
            tree = get_cached_tree()
            from utils import find_paths_for_title, remove_from_path, save_codex_tree
            
            paths = find_paths_for_title(tree, title)
            if paths:
                for path in paths:
                    tree = remove_from_path(tree, path, title)
                save_codex_tree(tree)
                log.info(f"Removed '{title}' from {len(paths)} category assignments")
        except Exception as e:
            log.error(f"Failed to remove from codex tree: {e}")
            # Don't fail the entire operation
        
        # 7. Remove from pending queue (if present)
        try:
            pending = load_pending_stories()
            original_count = len(pending)
            pending = [p for p in pending if p.get("title") != title]
            if len(pending) < original_count:
                save_pending_stories(pending)
                log.info(f"Removed '{title}' from pending queue")
        except Exception as e:
            log.error(f"Failed to remove from pending queue: {e}")
        
        # 8. Invalidate cache
        invalidate_cache()
        
        # 9. Auto-sync to GitHub
        try:
            from sync.github_sync import on_story_deleted
            on_story_deleted(book_slug, title)
        except Exception as e:
            log.debug(f"GitHub sync skipped: {e}")
        
        log.info(f"Successfully deleted story '{title}' from {book_slug}")
        
        return {
            "status": "success",
            "message": f"Story '{title}' deleted successfully",
            "book_slug": book_slug
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete story: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to delete story: {str(e)}")

# ------------------- EXPORT ------------------- #
@app.post("/api/export")
def export(body: ExportBody):
    result = export_stories(body.stories, format=body.format, is_single=body.is_single)
    if not result:
        raise HTTPException(500, "Export failed")
    return result # {mime, data (base64), filename}

# ------------------- MIGRATE DATABASE ------------------- #
@app.post("/api/migrate-db")
def migrate_database(user = Depends(require_editor)):
    """Recreate database tables to apply schema changes.
    WARNING: This will drop all existing data!
    """
    try:
        log.info("Starting database migration...")
        
        # Drop all tables
        from models import Base
        Base.metadata.drop_all(bind=engine)
        log.info("Dropped all existing tables")
        
        # Recreate all tables
        Base.metadata.create_all(bind=engine)
        log.info("Recreated all tables with new schema")
        
        # Reload stories from disk to repopulate
        sync_disk_to_db()
        
        # Clear and reload caches
        clear_book_metadata_cache()
        preload_book_metadata()
        invalidate_cache()
        
        return {
            "status": "success",
            "message": "Database migrated successfully. All data reloaded from disk."
        }
        
    except Exception as e:
        log.error(f"Migration failed: {e}", exc_info=True)
        raise HTTPException(500, f"Migration failed: {str(e)}")

# ------------------- RELOAD STORIES ------------------- #
@app.post("/api/reload-stories")
def reload_stories(user = Depends(require_editor)):
    """Force reload of stories from disk and sync to DB.
    Useful after running pre-processing scripts or updating story_positions.json files.
    """
    try:
        log.info("Manual reload triggered by user")
        
        # Perform full disk → DB sync
        sync_disk_to_db()
        
        # Clear and reload book metadata cache
        clear_book_metadata_cache()
        preload_book_metadata()
        
        # Invalidate cache to force tree reload
        invalidate_cache()
        
        # Force immediate reload to verify it worked
        tree = get_cached_tree()
        
        from utils import stories_dict
        return {
            "status": "success",
            "message": "Stories reloaded from disk and synced to database",
            "story_count": len(stories_dict),
            "tree_categories": len(tree)
        }
    except Exception as e:
        log.error(f"Reload failed: {e}", exc_info=True)
        raise HTTPException(500, f"Reload failed: {str(e)}")

# ------------------- CLEANUP SEARCH INDEX ------------------- #
@app.post("/api/cleanup-search-index")
def cleanup_search_index():
    """
    Remove orphaned entries from search indices.
    
    Finds stories in the search index that no longer exist in
    story_positions.json and removes them. Useful for fixing stale search
    results after story deletions.
    
    Note: No auth required - this is a safe cleanup operation that only
    removes entries not in story_positions.json.
    """
    from search import USE_DIRECT_SEARCH
    from utils import story_positions
    
    # Build set of all valid titles from story_positions
    valid_titles = set()
    for book_slug, positions in story_positions.items():
        valid_titles.update(positions.keys())
    
    log.info(f"Valid titles in story_positions: {len(valid_titles)}")
    
    orphaned_titles = set()
    deleted_count = 0
    
    try:
        if USE_DIRECT_SEARCH:
            # Direct FAISS + SQLite engine
            from search.engine import get_search_engine
            engine = get_search_engine()
            
            # Find orphaned titles in FAISS index
            for doc_id in list(engine.faiss_index.id_map):
                meta = engine.faiss_index.get_metadata(doc_id)
                if meta:
                    title = meta.get("title")
                    if title and title not in valid_titles:
                        orphaned_titles.add(title)
            
            log.info(f"Found {len(orphaned_titles)} orphaned titles in Direct search index")
            
            # Delete orphaned entries
            for title in orphaned_titles:
                count = engine.delete_by_title(title)
                deleted_count += count
                log.info(f"Removed orphaned story: '{title}' ({count} entries)")
            
            # Save updated indices
            if deleted_count > 0:
                engine.save()
        else:
            # Legacy Haystack document store
            from utils import document_store, document_store_path
            import numpy as np
            
            # Get all documents and find orphaned ones
            all_docs = list(document_store.filter_documents({}))
            log.info(f"Total documents in Haystack store: {len(all_docs)}")
            
            orphaned_doc_ids = []
            for doc in all_docs:
                title = doc.meta.get("title") if doc.meta else None
                if title and title not in valid_titles:
                    orphaned_titles.add(title)
                    orphaned_doc_ids.append(doc.id)
            
            log.info(f"Found {len(orphaned_titles)} orphaned titles ({len(orphaned_doc_ids)} documents)")
            
            # Delete orphaned documents
            if orphaned_doc_ids:
                document_store.delete_documents(orphaned_doc_ids)
                deleted_count = len(orphaned_doc_ids)
                
                # Convert remaining embeddings to lists before saving
                remaining_docs = list(document_store.filter_documents({}))
                docs_to_update = []
                for doc in remaining_docs:
                    if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                        doc.embedding = doc.embedding.tolist()
                        docs_to_update.append(doc)
                
                if docs_to_update:
                    document_store.delete_documents([doc.id for doc in docs_to_update])
                    document_store.write_documents(docs_to_update)
                
                document_store.save_to_disk(document_store_path)
                log.info(f"Saved updated Haystack document store")
        
        # Sync document store to GitHub so changes persist across deploys
        if deleted_count > 0:
            try:
                from sync.github_sync import sync_document_store, sync_documents_json
                sync_document_store(f"Cleanup: removed {len(orphaned_titles)} orphaned stories")
                sync_documents_json(f"Cleanup: removed {len(orphaned_titles)} orphaned stories")
                log.info("Synced document store to GitHub")
            except Exception as e:
                log.warning(f"Failed to sync document store to GitHub: {e}")
        
        # Invalidate caches
        invalidate_cache()
        
        return {
            "status": "success",
            "message": f"Cleaned up {len(orphaned_titles)} orphaned stories ({deleted_count} index entries)",
            "orphaned_titles": list(orphaned_titles),
            "valid_story_count": len(valid_titles),
            "synced_to_github": deleted_count > 0
        }
        
    except Exception as e:
        log.error(f"Search index cleanup failed: {e}", exc_info=True)
        raise HTTPException(500, f"Cleanup failed: {str(e)}")

# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)