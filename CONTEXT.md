# Preternatural Text Repository — Development Context

**Last Updated:** 2025-11-26  
**Purpose:** Quick reference for AI-assisted development. Consolidates architecture, module boundaries, and conventions.

---

## Project Overview

A scalable system for extracting, indexing, searching, and curating stories of preternatural phenomena from historical texts. React production frontend with FastAPI backend, semantic search powered by Haystack AI + FAISS.

**Current Scale:** 2 volumes processed; plans to expand to 100+

---

## High-Level Architecture

```
┌─────────────────┐      ┌─────────────────────┐      ┌─────────────┐
│   Data Layer    │ ───► │   Search Engine     │ ───► │     UI      │
│                 │      │                     │      │             │
│ books/          │      │ backend/main.py     │      │ frontend/   │
│ data/           │      │ backend/utils/      │      │ (React)     │
│ Pre-Processing/ │      │ (FastAPI)           │      │             │
└─────────────────┘      └─────────────────────┘      └─────────────┘
        │                         │                          │
        ▼                         ▼                          ▼
  document_store.json       /api/* endpoints          React components
  story_positions.json      Haystack pipelines        Zustand state
  codex_tree.json           JWT auth (Stack Auth)    Tailwind styling
```

---

## Core Domain Concepts

| Concept | Definition | Key Properties |
|---------|-----------|-----------------|
| **Story** | A discrete narrative unit extracted from source text | Has position markers (start/end), belongs to books, assignable to categories |
| **Book** | A source historical text (e.g., "Christian Mysticism Vol IV") | Contains multiple stories, has metadata (stories_meta.json), full text (Full_Text.md) |
| **Category/Node** | A taxonomy branch in the Codex Tree (e.g., "Demonic Activity") | Hierarchical, can have parent/children, contains multiple stories |
| **Codex Tree** | The full category taxonomy | Stored in `data/codex_tree.json`, sourced from PostgreSQL |
| **Tag Branch** | A filtered view scoped to a specific category and its stories | Used for browsing, search scoping |
| **Document Store** | Vector database of all story embeddings | Currently: in-memory JSON; planned: FAISS disk-backed |

---

## Module Responsibilities

### Backend

#### `backend/main.py` (44 KB)
- **Role:** FastAPI application entry point; all HTTP endpoints
- **Responsibilities:**
  - Search endpoint (`POST /api/search`)
  - Tree fetching (`GET /api/get-tree`)
  - Category operations (`POST /api/assign-category`, `POST /api/remove-category`)
  - Story rendering (`POST /api/render-story`)
  - Story creation (`POST /api/add-story`)
  - Authentication (Stack Auth JWT)
- **Key Points:** 
  - Heavy lifting delegated to `utils/` modules
  - Returns responses as Pydantic models
  - **Logging (P2-5 COMPLETE):** Uses `LOG_LEVEL` env var (default: INFO), RotatingFileHandler (10MB, 5 backups)

#### `backend/state.py` — Centralized State (NEW)

All global application state is now centralized in `state.py`:

```python
from state import app_state

# Access any global state
app_state.stories_dict      # {title: story_data}
app_state.books             # List of book slugs
app_state.sources           # ["All Sources"] + sorted book slugs
app_state.document_store    # Haystack InMemoryDocumentStore
app_state.USE_DB            # Database connection flag
app_state.SessionLocal      # SQLAlchemy session factory
```

**Benefits:**
- Eliminates circular import issues between modules
- Single source of truth for all shared state
- Modules can now be split into separate files cleanly
- Easier testing via state injection
- `discover_books()` called automatically on init

#### `backend/utils_legacy.py` — Backwards-Compatible Shim (~115 lines)

Thin shim that re-exports from new modules for backwards compatibility:

```python
# Old code still works:
from utils_legacy import search_stories, load_codex_tree, sources

# But new code should use:
from search import search_stories
from tree import load_codex_tree
from state import app_state
```

#### `backend/search/` — Search Module (NEW)

```
backend/search/
├── __init__.py      # Exports: document_store, pipelines, search_stories
├── pipelines.py     # Document store loading, embedder setup, pipeline construction
└── stories.py       # search_stories() - hybrid/semantic/keyword/exact modes
```

#### `backend/storage/` — Storage Module (NEW)

```
backend/storage/
├── __init__.py      # Exports all storage functions
├── books.py         # load_full_md, load/save_story_positions
├── stories.py       # update_story_boundaries, update_story_title
└── pending.py       # load/save_pending_stories, check_story_overlap
```

#### `backend/tree/` — Tree Module (NEW)

```
backend/tree/
├── __init__.py      # Exports: CATEGORIES, all tree functions
├── operations.py    # Pure functions: merge_trees, assign/remove_from_path, find_paths
└── persistence.py   # load/save_codex_tree (JSON + DB sync)
```

#### `backend/sync/` — Sync Module (NEW)

```
backend/sync/
├── __init__.py      # Exports sync functions
└── disk_to_db.py    # sync_disk_to_db, sync_books_from_metadata, load_all_stories, etc.
```

#### `backend/utils/` — Legacy Utils Wrapper

The original `backend/utils/` still works but now delegates to new modules:

```
backend/utils/
├── __init__.py      # Re-exports for backwards compatibility
├── tree_ops.py      # CATEGORIES, merge_trees, assign_to_path, etc.
├── cache.py         # get_cached_tree, get_book_metadata, preload, invalidate
├── rendering.py     # render_md_with_scroll_and_highlight, render_static_story
├── storage.py       # Re-exports storage functions
└── export.py        # export_stories, export_updated_jsons
```

**Import Priority:** `utils/__init__.py` imports from `utils_legacy` (which imports from new modules), then overrides with local module functions. The `assign_to_path` wrapper comes from `utils_legacy` to auto-provide `stories_dict`.

#### `backend/models.py`
- **Role:** SQLAlchemy ORM models
- **Entities:** User, Story, CodexNode, NodeStories, Book

### Frontend

#### `frontend/src/store.ts`
- **Role:** Zustand state management
- **Current State:** User auth, selected story, edit mode
- **Needs:** Tree caching (P3-3), search pagination state

#### `frontend/src/pages/SearchCurate.tsx` (900 lines)
- **Role:** Main search and curation UI
- **Current Issues:** 15+ useState hooks, tightly coupled concerns
- **Refactor Plan (P3-1):**
  - Extract to: `SearchPanel.tsx`, `SearchResults.tsx`, `StoryViewer.tsx`, `BoundaryEditor.tsx`, `NewStoryForm.tsx`, `CategoryAssignment.tsx`

#### `frontend/src/components/SidebarTree.tsx`
- **Role:** Codex tree navigation
- **Fetches:** Tree on every mount (should use store cache per P3-3)

#### `frontend/src/types/` (new)
- **Role:** TypeScript API response interfaces (P3-2)
- **Needed:** SearchQuery, SearchResult, BookResponse, CodexTree, etc.

### Data Layer

#### `books/{book_slug}/`
```
Full_Text.md              # Source text with [Page X] markers
story_positions.json      # {story_id: {start_char, end_char, page}}
Stories.md                # Extracted stories (markdown)
stories_meta.json         # {story_id: {title, summary, assigned_category}}
grouped_index.md          # Category-grouped index of stories
```

#### `data/`
```
document_store.json       # Haystack embeddings (46-58 KB each)
documents.json            # Document metadata
codex_tree.json           # Full category hierarchy
stories_dict.json         # Flat story lookup {story_id: story_obj}
pending_stories.json      # Stories awaiting ingestion
```

**Data Flow:**
1. Books processed via Pre-Processing scripts → `books/{slug}/` files
2. Backend loads files → embeds via Haystack → stores in `document_store.json`
3. Categories assigned via API → written to PostgreSQL + `codex_tree.json` sync
4. Frontend queries `/api/search` → results rendered + boundaries editable

---

## Key File Sizes & Performance Notes

| File | Size | Notes |
|------|------|-------|
| `backend/state.py` | ~175 lines | Centralized app state |
| `backend/utils_legacy.py` | ~115 lines | Thin backwards-compat shim |
| `backend/search/` | ~280 lines | pipelines.py + stories.py |
| `backend/storage/` | ~250 lines | books.py + stories.py + pending.py |
| `backend/tree/` | ~280 lines | operations.py + persistence.py |
| `backend/sync/` | ~230 lines | disk_to_db.py |
| `backend/utils/` | ~865 lines | Legacy wrapper modules |
| `backend/main.py` | 44 KB | FastAPI endpoints |
| `document_store.json` | 46-58 KB | FAISS migration planned (P0-2) |
| `documents.json` | 58 KB | Metadata bloat; consolidate to DB (P2-2) |
| `SearchCurate.tsx` | ~900 lines | Decompose (P3-1) |

**Current Story Count:** 933 stories across 2 books

---

## Search & Indexing

### Current Implementation (Haystack AI 2.x)
- **Hybrid Pipeline:** Combines BM25 keyword search + semantic embeddings
- **Embedder Model:** BAAI/bge-large-en-v1.5 (pre-downloaded, 1.3GB)
- **Document Store:** Currently InMemoryDocumentStore (loads all embeddings at startup)
- **Relevance Scoring:** Hybrid scoring from Haystack

### Query Flow
```
User Query → /api/search endpoint
  ↓
→ Haystack hybrid pipeline
  ├─ BM25 ranker (keyword matching)
  └─ Semantic ranker (embedding similarity)
  ↓
→ Results aggregated + sorted by score
  ↓
→ Rendered with /api/render-story for full text + boundaries
```

### Performance Issues
1. **Triple embedder load (P0-1):** 3 separate instances waste 2.4GB RAM + 15s startup
2. **In-memory document store (P0-2):** Doesn't scale past ~5000 stories
3. **N+1 queries on tree build (P1-1):** Every tree render hits DB 100+ times
4. **Embedding conversion overhead (P1-2):** numpy → list → numpy on every save

---

## Authentication & Permissions

**Provider:** Stack Auth (JWT-based)  
**Current Scope:** User login, story export per user  
**Important:** All search is currently global; no per-user permissions (could add in future)

---

## Conventions & Patterns

### Python Backend
- **Error Handling:** Raise HTTPException for user-facing errors
- **Logging:** Controlled by `LOG_LEVEL` env var (default INFO); set `LOG_LEVEL=DEBUG` for verbose output; logs rotate at 10MB (keeps 5 files)
- **File Paths:** Currently relative (`../books/`); should use pathlib with ROOT anchor (P2-4)
- **DB Queries:** Use SQLAlchemy ORM; avoid raw SQL

### React Frontend
- **State Management:** Zustand for global state; useState for component-local state
- **API Calls:** Wrapped in axios (`frontend/src/utils/axios.ts`)
- **Styling:** Tailwind CSS + custom `App.css`
- **Type Safety:** Minimal TypeScript currently; adding interfaces (P3-2)

### Data & JSON
- **Story IDs:** Unique per book; referenced across JSON files
- **Syncing:** Manual sync between JSON files and PostgreSQL (inefficient; see P2-2)
- **Backups:** Commit JSON files to git; no CI/CD backup process yet

---

## Critical Invariants

1. **A story can belong to multiple categories** — Don't assume 1-to-1 assignment
2. **Stories have fixed boundaries in source text** — Editable via UI, but must respect original page markers
3. **Search must filter by user permissions** (future) — Current code assumes all users see all stories
4. **Tree structure is hierarchical** — Parent nodes must exist before child assignments
5. **Embeddings are normalized** — Required for cosine similarity in FAISS
6. **Book full texts are immutable** — Don't modify `Full_Text.md` after embedding

---

## Deployment Notes

- **Research UI:** Deployed to HuggingFace Spaces via `app.py` (Gradio)
- **Production Backend:** Not currently deployed; runs locally
- **Frontend:** Not currently deployed; runs locally on `npm run dev`
- **Database:** PostgreSQL (local or remote per `.env.local`)

---

## Development Workflow

### Starting a new feature:
1. Pick a task from `TECH_DEBT_BACKLOG.md` (prioritized by phase)
2. Create a feature branch: `git checkout -b ai/task-name-YYYYMMDD`
3. Make changes locally; test with `npm run dev` or `pytest`
4. Review diffs; verify acceptance criteria from TECH_DEBT_BACKLOG
5. Commit to branch; push for review

### Running tests:
```bash
# Backend
cd backend
pytest test_model.py

# Frontend
cd frontend
npm run lint
npm run typecheck
```

### Key Scripts:
- `backend/migrate.py` — Update PostgreSQL schema
- `backend/ingest_book.py` — Add new book to index
- `pre_processing/` — Text extraction scripts (private)

---

## Quick Links

- **README:** Full setup instructions and API reference
- **REPO_SUMMARY.md:** Detailed agent breakdown (for reference; agent system deprecated)
- **TECH_DEBT_BACKLOG.md:** Prioritized refactoring tasks
- **Haystack Docs:** https://docs.haystack.deepset.ai/
- **BAAI/bge Embedder:** https://huggingface.co/BAAI/bge-large-en-v1.5

---

## When Working with AI Assistants

**Context to Include:**
- Task ID from TECH_DEBT_BACKLOG (e.g., "P2-1")
- Specific files involved
- Expected behavior from acceptance criteria

**Context to Exclude (to save tokens):**
- The entire `document_store.json` or `documents.json`
- Full `backend/utils.py` unless needed for the specific function
- Large JSON exports from searches

**Safe Patterns:**
- Ask AI to read specific line ranges: "Read `backend/utils.py` lines 337-362"
- Request diffs, not full file rewrites
- Always verify changes don't break existing tests
- Review diffs carefully for architectural coherence

