# backend/main.py
import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import jwt
# ------------------------------------------------------------------ #
# 1. Logging
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)
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
# 3. Paths (relative to repo root)
# ------------------------------------------------------------------ #
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_DIR = os.path.join(ROOT, "books")
DATA_DIR = os.path.join(ROOT, "data")
# ------------------------------------------------------------------ #
# 4. Import utils **after** paths are defined
# ------------------------------------------------------------------ #
from utils import (
    document_store, both_pipeline, keyword_pipeline, semantic_pipeline,
    search_stories, load_codex_tree, save_codex_tree,
    assign_to_path, remove_from_path,
    render_md_with_scroll_and_highlight, render_static_story,
    export_stories, get_stories_at_path, find_paths_for_title,
    load_story_positions, # needed for render fallback
)
# ------------------------------------------------------------------ #
# 5. Startup – sanity check
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
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Neon uses RS256; fetch public key from JWKS
        jwks_url = "https://auth.neon.tech/.well-known/jwks.json"
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="neon-auth",  # Adjust if needed
            options={"verify_exp": True}
        )
        return payload
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {str(e)}")

async def require_editor(user = Depends(get_current_user)):
    if user.get("role") != "editor":
        raise HTTPException(403, "Editor role required")
    return user
# ------------------------------------------------------------------ #
# 6. Pydantic models (pattern instead of regex)
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
# ------------------------------------------------------------------ #
# 7. End-points
# ------------------------------------------------------------------ #
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
@app.get("/api/get-stories/{path:path}")
def get_stories(path: str):
    """path is slash-separated, e.g. Demonic Activity/Obsession/Fear/Anxiety"""
    parts = [p.strip() for p in path.split("/") if p.strip()]
    tree = load_codex_tree()
    return get_stories_at_path(tree, parts)
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
async def assign_category(body: AssignBody, user = Depends(require_editor)):
    tree = load_codex_tree()
    updated = assign_to_path(tree, body.path, body.story)
    save_codex_tree(updated)
    return {"status": "assigned"}
@app.delete("/api/remove-category")
async def remove_category(body: RemoveBody, user = Depends(require_editor)):
    tree = load_codex_tree()
    updated = remove_from_path(tree, body.path, body.title)
    save_codex_tree(updated)
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
    if body.mode == "static":
        return {"html": render_static_story(story)}
    else: # book mode
        html = render_md_with_scroll_and_highlight(
            book_slug=story["book_slug"],
            start_char=story["start_char"],
            end_char=story["end_char"],
            page=story["pages"].split("-")[0],
            search_query=body.search_query,
        )
        return {"html": html}
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