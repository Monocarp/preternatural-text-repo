# Preternatural Text Repository — Development Context

**Last Updated:** 2025-11-29  
**Purpose:** Quick reference for AI-assisted development.

---

## Project Overview

A scalable system for extracting, indexing, searching, and curating stories of preternatural phenomena from historical texts. React frontend + FastAPI backend with hybrid semantic search.

**Current Scale:** 5 volumes, 900+ stories  
**Target Scale:** 100+ volumes

---

## Quick Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│   books/    │ ───► │     backend/     │ ───► │  frontend/  │
│   data/     │      │  (FastAPI)       │      │  (React)    │
└─────────────┘      └──────────────────┘      └─────────────┘
                            │
              ┌─────────────┴─────────────┐
              │    search/                │
              │  FAISS + SQLite FTS5      │
              │  (Direct engine)          │
              └───────────────────────────┘
```

---

## Directory-Specific Context Files

**Read these first for detailed info:**

| Directory | Context File | Key Info |
|-----------|--------------|----------|
| `backend/` | `backend/CONTEXT.md` | API endpoints, modules, auth |
| `backend/search/` | `backend/search/CONTEXT.md` | **Search engine architecture** |
| `frontend/` | `frontend/CONTEXT.md` | React pages, components, styling |
| `data/` | `data/CONTEXT.md` | Data files (what NOT to read) |

---

## Recent Major Changes (Nov 2025)

1. **Search Engine Migration:** Haystack → Direct FAISS + SQLite FTS5
   - 10x faster startup (11.5s → 0.7s)
   - 3x faster search (0.5s → 0.14s)
   - Feature flag: `USE_DIRECT_SEARCH=true`

2. **Story Review Tab:** Visual editor in BookDetail showing all stories highlighted
   - Click-to-select stories in full text
   - Inline boundary editing with auto-scroll
   - Edit title, delete story, add new story

3. **Responsive UI:** Auto-collapsing sidebar, mobile-friendly layouts

4. **Full Text Typography:** Libre Baskerville font, markdown rendering

5. **Frontend Hooks Refactoring:** Extracted shared logic from large components
   - Custom hooks: `useKeywordsEditor`, `useCategoryAssignment`, `useNewStoryCreator`, `useBoundaryEditor`
   - SearchCurate.tsx reduced from 1300 to 900 lines (30% reduction)
   - See `frontend/CONTEXT.md` for hook documentation

6. **Backend Error Handling:** Standardized exception patterns across all modules
   - Custom exceptions in `backend/utils/exceptions.py`
   - Consistent error responses with `error_response()` helper

---

## Key Entry Points

| Task | Where to Look |
|------|---------------|
| Search implementation | `backend/search/engine.py` |
| API endpoints | `backend/main.py` |
| Frontend routing | `frontend/src/main.tsx` |
| Story rendering | `backend/utils/rendering.py` |
| Database models | `backend/models.py` |
| Story Review UI | `frontend/src/pages/BookDetail.tsx` |
| Book ingestion | `backend/ingest_book.py` |

---

## Environment Variables

```bash
# .env.local
DATABASE_URL=postgresql://...      # Neon PostgreSQL
USE_DIRECT_SEARCH=true             # Use new search engine
ENABLE_RERANKER=false              # Cross-encoder (disabled)
EDITOR_EMAILS=email1,email2        # Editor access list
DISABLE_AUTH=true                  # Local dev only
GITHUB_TOKEN=ghp_xxx               # Auto-sync changes to GitHub (production)
GITHUB_REPO=Monocarp/preternatural-text-repo  # Target repo (optional)
```

---

## What NOT to Read (Save Tokens)

- `data/*.faiss`, `data/*.db` - Binary files
- `data/document_store.json`, `data/documents.json` - Large JSON
- `backend/models/bge-large-en-v1.5/` - Model weights (1.3GB)
- `__pycache__/`, `node_modules/` - Generated files
- `venv/` - Python virtual environment

---

## Development Commands

```bash
# Backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm run dev

# With env vars (PowerShell)
$env:USE_DIRECT_SEARCH='true'; $env:DISABLE_AUTH='true'; python -m uvicorn main:app --port 8000
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Tailwind CSS v4, Zustand |
| Backend | FastAPI, Python 3.11+ |
| Search | FAISS (vectors), SQLite FTS5 (BM25), SentenceTransformers |
| Database | PostgreSQL (Neon) |
| Auth | Stack Auth (JWT) |
| Hosting | Vercel (frontend), Render (backend) |

---

## Core Concepts

| Concept | Definition |
|---------|-----------|
| **Story** | A narrative unit extracted from source text with position markers |
| **Book** | A source text containing multiple stories |
| **Codex Tree** | Hierarchical category taxonomy for organizing stories |
| **Search Mode** | Hybrid (default), Semantic, Keyword, or Exact |

---

## Critical Invariants (Do Not Break)

1. **PostgreSQL is source of truth** - JSON files are read caches
2. **Embeddings must be normalized** - FAISS uses inner product = cosine only for unit vectors
3. **Full_Text.md is immutable** - Changing it invalidates all character positions
4. **Stories can belong to multiple categories** - Don't assume 1-to-1
5. **Sidebar is per-page** - Each page renders its own `<SidebarTree />`
6. **API calls through axios wrapper** - Never use raw fetch()

---

## Making Architectural Changes

### Before changing search:
- Read `backend/search/CONTEXT.md` for score thresholds, RRF fusion
- Test with `USE_DIRECT_SEARCH=true` and `=false` for comparison
- Check lazy loading isn't broken (startup should be <1s)

### Before changing database:
- Update `backend/models.py`
- Run migration in `backend/migrate.py`
- Update JSON sync in `backend/tree/persistence.py` if tree-related

### Before changing frontend layout:
- Test at 1024px, 768px, and 1440px+ widths
- Sidebar auto-collapses at <1024px
- Use `min-w-0` on flex children to allow shrinking

---

## For Detailed Documentation

- `backend/CONTEXT.md` - Backend architecture, endpoints, auth
- `backend/search/CONTEXT.md` - Search engine internals
- `frontend/CONTEXT.md` - React pages, components, styling
- `data/CONTEXT.md` - Data files and what NOT to read
- `documentation/TECH_DEBT_BACKLOG.md` - Remaining improvement tasks

