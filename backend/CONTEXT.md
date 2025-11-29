# Backend Context

**Last Updated:** 2025-11-27

## Quick Overview

FastAPI backend serving the Preternatural Text search and curation system.

## Architecture

```
backend/
├── main.py           # FastAPI app, all HTTP endpoints (~1100 lines)
├── models.py         # SQLAlchemy ORM: User, Story, Book, CodexNode
├── state.py          # Centralized app state (app_state singleton)
├── utils_legacy.py   # Backwards-compat shim for old imports
├── ingest_book.py    # CLI script to ingest books into PostgreSQL
├── search/           # NEW: Direct FAISS + SQLite search engine
├── storage/          # Book/story file operations
├── tree/             # Codex tree operations
├── sync/             # Disk ↔ DB synchronization
└── utils/            # Rendering, caching, exports
```

## Critical Architectural Decisions

### 1. Centralized State (`state.py`)
All shared state goes through `app_state` singleton:
```python
from state import app_state
app_state.stories_dict      # {title: story_data}
app_state.books             # List of book slugs  
app_state.sources           # ["All Sources"] + book slugs
app_state.SessionLocal      # SQLAlchemy session factory
```
**Why:** Eliminates circular imports between modules. Any new module needing shared state should import from `state.py`, not create its own globals.

### 2. Dual Persistence (PostgreSQL + JSON)
- **PostgreSQL (Neon):** Canonical source for stories, books, categories
- **JSON files:** `codex_tree.json`, `stories_dict.json` for fast reads
- **Sync:** `tree/persistence.py` writes to both on mutations

**Invariant:** Always write to DB first, then sync to JSON. Never trust JSON as source of truth for writes.

### 3. Search Engine (FAISS + SQLite)
See `backend/search/CONTEXT.md` for details. Key points:
- Feature flag `USE_DIRECT_SEARCH=true` enables new engine
- Falls back to Haystack if flag is false
- Embeddings use BAAI/bge-large-en-v1.5 (1024 dimensions)

### 4. Book Structure
Each book lives in `books/{slug}/`:
```
books/ecology_of_souls_volume_i/
├── Full_Text.md          # Source text with [Page X] markers
├── story_positions.json  # {title: {start_char, end_char, pages, keywords}}
├── stories_meta.json     # Additional metadata
└── Stories.md            # Extracted stories (generated)
```
**Invariant:** `Full_Text.md` is immutable after embedding. Changing it invalidates all character positions.

## Module Dependencies

```
main.py
  ├── models.py (ORM)
  ├── state.py (app_state)
  ├── search/ (search_stories)
  ├── tree/ (load_codex_tree, assign_to_path)
  ├── storage/ (load_full_md, update_story_boundaries)
  ├── sync/ (sync_disk_to_db)
  └── utils/ (rendering, caching)

search/
  ├── engine.py ← faiss_index.py, fts_index.py
  ├── stories_direct.py ← engine.py
  └── engine_compat.py ← stories_direct.py (wrapper)

state.py
  └── NO DEPENDENCIES (intentionally isolated)
```

## Key Endpoints (main.py)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/search` | POST | No | Hybrid search |
| `/api/get-tree` | GET | No | Fetch codex tree |
| `/api/assign-category` | POST | Editor | Add story to category |
| `/api/remove-category` | POST | Editor | Remove story from category |
| `/api/render-story` | POST | No | Get story HTML with highlighting |
| `/api/update-boundaries` | POST | Editor | Edit story char positions |
| `/api/update-title` | POST | Editor | Rename a story |
| `/api/update-keywords` | POST | Editor | Edit story keywords |
| `/api/add-story` | POST | Editor | Create new story |
| `/api/delete-story/{title}` | DELETE | Editor | Remove story from all stores |
| `/api/books` | GET | No | List all books |
| `/api/books/{slug}` | GET | No | Get book details + stories |
| `/api/full-text/{slug}` | GET | No | Get full book text |

## Database Schema (models.py)

```
User (id, email, name, role)
  └── role: "viewer" | "editor"

Book (id, slug, title, author, year)
  └── stories: [Story]

Story (id, title, book_slug, start_char, end_char, pages, keywords)
  └── Unique constraint: (title, book_slug)

CodexNode (id, path, name, parent_id)
  └── Hierarchical via parent_id

NodeStories (node_id, story_title)
  └── Many-to-many: stories can belong to multiple categories
```

## Authentication Flow

1. Frontend sends JWT from Stack Auth in `Authorization: Bearer <token>`
2. `get_current_user()` validates token, returns user dict
3. `require_editor()` dependency checks `user.role == "editor"`
4. Editor emails auto-promoted on first protected endpoint hit



## Error Handling Patterns

```python
# User-facing errors
raise HTTPException(404, "Story not found")
raise HTTPException(403, "Editor role required")

# Internal errors - log and return 500
try:
    ...
except Exception as e:
    log.error(f"Failed to X: {e}")
    raise HTTPException(500, f"Internal error: {str(e)}")
```

## Adding a New Feature Checklist

1. **New endpoint:** Add to `main.py`, use Pydantic models for request/response
2. **New shared state:** Add to `state.py`, access via `app_state.X`
3. **New search feature:** Modify `search/engine.py` or `search/stories_direct.py`
4. **New storage operation:** Add to appropriate `storage/` module
5. **Database change:** Update `models.py`, run migration

## Don't Read These Files (Large/Binary)

- `models/bge-large-en-v1.5/` - Embedding model weights (1.3GB)
- `__pycache__/` - Python bytecode
- Any `.faiss` or `.db` files - Binary data
