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

# ------------------------------------------------------------------ #
# 1. Logging
# ------------------------------------------------------------------ #
# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

# Set up file and console logging
log_file = os.path.join(log_dir, "backend.log")
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[file_handler, console_handler],
)
log = logging.getLogger(__name__)
log.info(f"Logging to file: {log_file}")
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
    search_stories, load_codex_tree, save_codex_tree,
    assign_to_path, remove_from_path,
    render_md_with_scroll_and_highlight, render_static_story,
    export_stories, get_stories_at_path, find_paths_for_title,
    load_story_positions, update_story_boundaries, sources, # needed for render fallback
)
# ------------------------------------------------------------------ #
# 6. Startup – sanity check
# ------------------------------------------------------------------ #
@app.on_event("startup")
async def startup():
    if document_store is None:
        raise RuntimeError("document_store failed to initialise")
    load_codex_tree() # warms the global tree + stories_dict
    # Warm-up embedding model
    log.info("Warming up embedding model...")
    dummy_results = both_pipeline.run({
        "embedder": {"text": "warmup query"},
        "retriever_embedding": {"top_k": 1, "filters": None},
        "retriever_bm25": {"query": "warmup query", "top_k": 1, "filters": None}
    })
    log.info("Embedding model warmed up")
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

        if not db_user or db_user.role != "editor":
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
    results = search_stories(
        query=body.query,
        source_filter=body.source_filter,
        type_filter=body.type_filter,
        search_mode=body.search_mode,
        top_k=body.top_k,
        min_score=body.min_score,
    )
    return {"results": results}
# ------------------- TREE ------------------- #
@app.get("/api/get-tree")
def get_tree():
    return load_codex_tree()
# ------------------- SOURCES ------------------- #
@app.get("/api/sources")
def get_sources():
    return {"sources": sources}
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
def get_stories(path: str):
    log.info(f"Raw path received: {repr(path)}")
    parts = [urllib.parse.unquote(p.strip()) for p in path.split("/") if p.strip()]
    log.info(f"After split and decode: {parts}")
    tree = load_codex_tree()
    log.info(f"Getting stories for path: {parts}")
    log.info(f"Tree structure at root: {list(tree.keys())[:5]}...")  # First 5 keys
    stories = get_stories_at_path(tree, parts)
    log.info(f"Found {len(stories)} stories for path {parts}")
    if len(stories) == 0 and len(parts) > 0:
        # Debug: check what we find at each level
        current = tree
        for i, part in enumerate(parts):
            log.info(f"Level {i}: looking for '{part}' in {list(current.keys()) if isinstance(current, dict) else type(current)}")
            if part in current:
                current = current[part]
                log.info(f"Found '{part}', continuing...")
            else:
                log.info(f"'{part}' not found, stopping")
                break
        log.info(f"Final current: {current}")
    return stories
@app.get("/api/get-unassigned")
def get_unassigned():
    tree = load_codex_tree()
    from utils import stories_dict
    assigned = set()
    def walk(node):
        if isinstance(node, dict):
            if "_stories" in node:
                assigned.update(node["_stories"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            assigned.update(node)
    walk(tree)
    unassigned = [s for t, s in stories_dict.items() if t not in assigned]
    return unassigned
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
    
    tree = load_codex_tree()
    updated = assign_to_path(tree, body.path, body.story)
    # Save to JSON only (like original app.py) - database is already updated via direct assignment
    save_codex_tree_to_json(updated)
    if stories_dict:
        with open(stories_dict_path, "w") as f:
            json.dump(stories_dict, f, indent=4)
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
    from utils import remove_from_path, save_codex_tree_to_json, load_codex_tree
    tree = load_codex_tree()
    updated = remove_from_path(tree, body.path, body.title)
    save_codex_tree_to_json(updated)
    
    return {"status": "removed"}
# ------------------- RENDER ------------------- #
@app.post("/api/render-story")
def render_story(body: RenderQuery):
    from utils import stories_dict, find_book_slug
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
# ------------------- EXPORT ------------------- #
@app.post("/api/export")
def export(body: ExportBody):
    result = export_stories(body.stories, format=body.format, is_single=body.is_single)
    if not result:
        raise HTTPException(500, "Export failed")
    return result # {mime, data (base64), filename}
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)