# Technical Debt Backlog — Preternatural Text Repository
Generated: 2025-11-25 | Updated: 2025-11-26

## How to Use This File
1. Pick a task from your current phase
2. Review the task spec and acceptance criteria
3. Work on changes in a feature branch
4. Verify acceptance criteria are met
5. Mark task as ✅ when merged

---

## Phase 1: Performance Critical (Week 1)

### P0-1: Fix Triple Embedding Model Load ⚠️ BLOCKED BY HAYSTACK
**Files:** `backend/search/pipelines.py`  
**Effort:** N/A (Haystack limitation)  
**Impact:** Limited - model weights are cached by SentenceTransformers library

**Problem:** Currently 3 embedder instances exist:
1. `embedder_both` - SentenceTransformersTextEmbedder for hybrid pipeline
2. `embedder_sem` - SentenceTransformersTextEmbedder for semantic-only pipeline  
3. `embedder_doc` - SentenceTransformersDocumentEmbedder for batch indexing

**Investigation Results (2025-11-26):**
```
Haystack does NOT allow sharing component instances between pipelines.
Error: "Component has already been added in another Pipeline. 
Components can't be shared between Pipelines."

However, the SentenceTransformers library caches model weights after first load,
so the second/third embedder warm_up() is fast (reuses cached weights).

Actual memory impact is lower than estimated because:
- Model weights are shared at the PyTorch level (same tensors in GPU/CPU memory)
- Only the wrapper objects are duplicated (~few KB each)
```

**Alternative Approaches (Future):**
1. Use raw SentenceTransformer directly instead of Haystack embedders
2. Create a custom Haystack component that wraps a shared model
3. Wait for Haystack to add component sharing support

**Status:** ⚠️ Blocked - Haystack architecture limitation. Low priority since actual RAM impact is minimal.

---

### P0-2: Migrate Document Store to Disk-Backed FAISS
**Files:** `backend/utils.py` (document store setup), `data/document_store.json`  
**Effort:** 8 hours  
**Impact:** -500MB+ RAM, enables 100K+ document scaling

**Problem:** InMemoryDocumentStore loads all embeddings into RAM on every startup.

**Task Spec:**
```
Replace InMemoryDocumentStore with FAISSDocumentStore using disk-backed indices.
- Use FAISS IndexFlatIP for cosine similarity (embeddings are normalized)
- Store index at data/faiss_index.bin
- Keep metadata in SQLite sidecar (data/faiss_metadata.db)
- Update save/load functions to use new format
- Migrate existing document_store.json to new format (one-time script)
```

**Acceptance Criteria:**
- [ ] Document store loads in <2s regardless of corpus size
- [ ] RAM usage <200MB for document store (vs current 500MB+)
- [ ] All search modes (hybrid, semantic, keyword) still work
- [ ] Existing embeddings migrated without re-embedding

**Status:** ⬜ Not started

**Note:** This changes how `document_store.json` is consumed. Plan migration carefully.

---

### P0-3: Add LRU Cache for Full Text Loading ✅ COMPLETE
**Files:** `backend/storage/books.py`  
**Effort:** 1 hour  
**Impact:** -100-300ms per story render, reduced disk I/O

**Completed 2025-11-26:**

Added `@lru_cache(maxsize=10)` to `load_full_md()`:
- Second load of same book is instant (cache hit)
- Cache bounded to 10 most recently used books
- Added `clear_full_md_cache()` for manual invalidation
- Added `get_full_md_cache_info()` for debugging

**Test Results:**
```
First load: 1406087 chars (disk read)
Second load: 1406087 chars (cache hit)
Cache info: CacheInfo(hits=1, misses=1, maxsize=10, currsize=1)
```

**Status:** ✅ Complete

---

## Phase 2: Scalability (Week 2)

### P1-1: Fix N+1 Query Pattern in Tree Loading
**Files:** `backend/utils.py` lines 642-756  
**Effort:** 4 hours  
**Impact:** -2-5s on /api/get-tree endpoint

**Problem:** Recursive tree builder queries each node individually.

**Task Spec:**
```
Refactor build_tree_from_db() to load all CodexNodes and NodeStories in 2 queries,
then build tree in-memory:
1. SELECT * FROM codex_nodes (with parent_id)
2. SELECT node_id, story_id, title FROM node_stories JOIN stories
3. Build tree dict in Python using parent_id relationships
```

**Acceptance Criteria:**
- [ ] /api/get-tree responds in <200ms (vs current 2-5s)
- [ ] Database queries reduced to 2-3 (vs current 100+)
- [ ] Tree structure identical to current output

**Status:** ⬜ Not started

---

### P1-2: Fix Embedding Conversion Loop on Save
**Files:** `backend/utils.py` lines 330-338, `backend/main.py` lines 458-468  
**Effort:** 4 hours  
**Impact:** -2-5s per story add/update

**Problem:** All embeddings converted numpy→list→numpy on every save.

**Task Spec:**
```
After P0-2 (FAISS migration), this is mostly solved. If still using JSON:
- Use numpy's .npy format for embeddings
- Implement incremental updates (only write changed documents)
- Or use HDF5 for efficient partial reads/writes
```

**Depends on:** P0-2 (FAISS migration)

**Status:** ⬜ Blocked by P0-2

---

### P1-3: Move Tree Writes to Background Queue
**Files:** `backend/main.py` lines 377-425  
**Effort:** 6 hours  
**Impact:** -500-2000ms per category assignment

**Problem:** Category assignments block HTTP response while writing to DB + JSON + rebuilding tree.

**Task Spec:**
```
1. Add FastAPI BackgroundTasks to assign/remove endpoints
2. Return optimistic response immediately with new assignment
3. Queue actual persistence (DB write, JSON save, cache invalidation)
4. Add /api/sync-status endpoint to check if background tasks are complete
```

**Acceptance Criteria:**
- [ ] /api/assign-category returns in <100ms
- [ ] Background task completes within 5s
- [ ] No data loss if server restarts mid-task
- [ ] Frontend can poll sync status if needed

**Status:** ⬜ Not started

---

### P1-4: Fix Global Mutable Cache State
**Files:** `backend/utils.py` lines 23-38, 53-60  
**Effort:** 4 hours  
**Impact:** Eliminates race conditions in concurrent requests

**Problem:** Module-level globals don't share state across uvicorn workers.

**Task Spec:**
```
Replace global _tree_cache, _cache_timestamp with:
Option A (simple): File-based cache with atomic writes + mtime checking
Option B (scalable): Redis cache with TTL and atomic operations

For MVP, Option A is sufficient:
- Write cache to data/tree_cache.json
- Check file mtime vs _cache_timestamp before reads
- Use tempfile + atomic rename for writes
```

**Acceptance Criteria:**
- [ ] Multiple uvicorn workers see consistent cache
- [ ] Cache invalidation propagates within 1s
- [ ] No race conditions under concurrent load

**Status:** ⬜ Not started

---

## Phase 3: Maintainability (Week 3-4)

### P2-1: Split Monolithic utils.py into Modules ✅ COMPLETE
**Files:** `backend/utils.py` → `backend/utils/` + `backend/utils_legacy.py` + new modules  
**Effort:** 8 hours  
**Impact:** Faster development, easier testing

**Completed 2025-11-26:**

**New Module Architecture:**
```
backend/
├── state.py              # Centralized app state (all globals)
├── utils_legacy.py       # Thin shim (~115 lines) - re-exports for backwards compat
├── search/
│   ├── __init__.py       # Exports: document_store, pipelines, search_stories
│   ├── pipelines.py      # Document store, embedder setup, pipeline construction
│   └── stories.py        # search_stories() - hybrid/semantic/keyword/exact
├── storage/
│   ├── __init__.py       # Exports all storage functions
│   ├── books.py          # load_full_md, load/save_story_positions
│   ├── stories.py        # update_story_boundaries, update_story_title
│   └── pending.py        # load/save_pending_stories, check_story_overlap
├── tree/
│   ├── __init__.py       # Exports: CATEGORIES, all tree functions
│   ├── operations.py     # Pure functions: merge_trees, assign/remove_from_path
│   └── persistence.py    # load/save_codex_tree (JSON + DB sync)
├── sync/
│   ├── __init__.py       # Exports sync functions
│   └── disk_to_db.py     # sync_disk_to_db, sync_books_from_metadata, etc.
└── utils/                # Legacy wrapper (delegates to new modules)
    ├── __init__.py       # Re-exports for backwards compatibility
    ├── tree_ops.py       # CATEGORIES, merge_trees, etc.
    ├── cache.py          # get_cached_tree, get_book_metadata
    ├── rendering.py      # render_md_with_scroll_and_highlight
    ├── storage.py        # Re-exports storage functions
    └── export.py         # export_stories, export_updated_jsons
```

**Reduction achieved:**
- Started: ~1860 lines in utils_legacy.py
- Final: ~115 lines in utils_legacy.py (thin shim)
- **~1745 lines extracted into focused modules**

**Key Design Decisions:**
- `state.py` holds ALL shared state - eliminates circular imports
- `discover_books()` called automatically on AppState init
- `utils_legacy.py` is now just a thin shim for backwards compatibility
- New code should import from `search`, `storage`, `tree`, `sync` directly
- `assign_to_path` wrapper in utils_legacy auto-provides `stories_dict`

**Status:** ✅ Complete

---

### P2-2: Consolidate to Single Source of Truth (PostgreSQL)  
**Files:** `backend/utils.py`, `backend/main.py`, `data/codex_tree.json`  
**Effort:** 8 hours  
**Impact:** Eliminates data inconsistency bugs

**Problem:** Both JSON files and PostgreSQL store the same data with manual sync.

**Task Spec:**
```
Phase A (Data Migration):
- Add migration to ensure all JSON data is in PostgreSQL
- Update story_positions.json → stories table sync

Phase B (Code Changes):
- Remove all JSON writes for codex_tree
- Read exclusively from PostgreSQL
- Keep JSON as read-only backup (generate on demand for export)
```

**Acceptance Criteria:**
- [ ] All reads come from PostgreSQL
- [ ] JSON files only written for backup/export
- [ ] No "tree out of sync" bugs possible

**Status:** ⬜ Not started

---

### P2-3: Add Search Result Pagination
**Files:** `backend/main.py` line 190, `frontend/src/pages/SearchCurate.tsx`  
**Effort:** 6 hours  
**Impact:** -3-5s render time, -500KB-2MB network

**Problem:** Search returns up to 5000 results, frontend renders all.

**Task Spec:**
```
Backend:
- Add offset/limit params to /api/search (default limit=50)
- Return total_count in response for pagination UI
- Add cursor-based pagination option for stability

Frontend:
- Add "Load More" button or infinite scroll
- Use react-window for virtual scrolling of results
- Show "X of Y results" count
```

**Acceptance Criteria:**
- [ ] Initial search returns 50 results in <500ms
- [ ] "Load More" fetches next 50
- [ ] 1000+ results render smoothly with virtualization

**Status:** ⬜ Not started

**Note:** Changes `/api/search` response shape — update frontend accordingly.

---

### P2-4: Fix Hardcoded File Paths ✅ COMPLETE
**Files:** `backend/state.py`  
**Effort:** 2 hours  
**Impact:** Eliminates deployment failures

**Completed 2025-11-26:**

Updated `state.py` to use `pathlib` with absolute paths:
```python
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent

# All paths are now absolute Path objects:
self.books_dir = ROOT_DIR / "books"
self.data_dir = ROOT_DIR / "data"
self.document_store_path = self.data_dir / "document_store.json"
# etc.
```

**Verified:**
- ✅ Scripts work from any working directory
- ✅ Paths resolve correctly to absolute paths
- ✅ All existing functionality still works

**Note:** Other files still use `os.path.join()` but they work with Path objects.
Can be cleaned up incrementally if desired.

**Status:** ✅ Complete

---

### P2-5: Fix Excessive Logging ✅ COMPLETE
**Files:** `backend/main.py` lines 22-29  
**Effort:** 1 hour  
**Impact:** -10GB+ logs/day, easier debugging

**Completed 2025-11-26:**
- Added `LOG_LEVEL` environment variable (default: INFO)
- Replaced FileHandler with RotatingFileHandler (10MB max, 5 backups)
- Downgraded verbose path traversal logs from `info` to `debug`
- Downgraded tree merge logs from `info` to `debug`
- Console always INFO+, file respects LOG_LEVEL

**To enable debug logging:** Set `LOG_LEVEL=DEBUG` in environment

**Status:** ✅ Complete

---

## Phase 4: Polish (Week 5)

### P3-1: Decompose SearchCurate.tsx Component
**Files:** `frontend/src/pages/SearchCurate.tsx`  
**Effort:** 8 hours  
**Impact:** Faster feature development, fewer state bugs

**Problem:** 900-line component with 15+ useState hooks.

**Task Spec:**
```
Extract into:
frontend/src/
  pages/
    SearchCurate.tsx         # Orchestrator, layout only
  components/
    search/
      SearchPanel.tsx        # Query form, filters
      SearchResults.tsx      # Results list with virtualization
    story/
      StoryViewer.tsx        # Static/book mode rendering
      BoundaryEditor.tsx     # Edit mode with text selection
      NewStoryForm.tsx       # New story creation
    category/
      CategoryAssignment.tsx # Path selection, assign/remove

Use React Context or Zustand for shared state (selectedStory, editMode, etc.)
```

**Acceptance Criteria:**
- [ ] No component exceeds 200 lines
- [ ] Each component is independently testable
- [ ] State bugs from hook interdependencies eliminated

**Status:** ⬜ Not started

---

### P3-2: Add TypeScript Types for API Responses
**Files:** `frontend/src/types/` (new directory)  
**Effort:** 4 hours  
**Impact:** Catch API schema mismatches at compile time

**Problem:** Only one interface defined, rest is `any`.

**Task Spec:**
```
Create frontend/src/types/api.ts with interfaces matching backend Pydantic models:
- SearchQuery, SearchResult
- BookResponse, StoryObject
- CodexTree, AssignBody, RemoveBody
- RenderQuery, UpdateBoundariesBody
- etc.

Update all API calls to use typed responses.
```

**Acceptance Criteria:**
- [ ] All API responses have TypeScript types
- [ ] TypeScript errors on schema mismatches
- [ ] Autocomplete works for API response fields

**Status:** ⬜ Not started

---

### P3-3: Cache Tree Globally in Frontend
**Files:** `frontend/src/pages/SearchCurate.tsx`, `frontend/src/components/SidebarTree.tsx`, `frontend/src/store.ts`  
**Effort:** 2 hours  
**Impact:** Eliminate redundant tree fetches

**Problem:** Tree fetched on every component mount.

**Task Spec:**
```
Move tree loading to Zustand store with:
- loadTree() only fetches if stale (>60s) or forced
- Tree state shared across all components
- Invalidate on category assign/remove
```

**Acceptance Criteria:**
- [ ] Tree fetched once per session (or on invalidation)
- [ ] Navigation between pages doesn't re-fetch
- [ ] Assign/remove properly invalidates cache

**Status:** ⬜ Not started

---

## Progress Tracker

| Phase | Total Tasks | Completed | % Done |
|-------|-------------|-----------|--------|
| Phase 1 (P0) | 3 | 1 (1 blocked) | 33% |
| Phase 2 (P1) | 4 | 0 | 0% |
| Phase 3 (P2) | 5 | 3 | 60% |
| Phase 4 (P3) | 3 | 0 | 0% |
| **Total** | **15** | **4** | **27%** |

---

## Quick Reference

| Task | Summary | Files |
|------|---------|-------|
| P0-1 | Consolidate embedder instances | `backend/search/pipelines.py` |
| P0-2 | FAISS migration | `backend/search/pipelines.py`, `data/` |
| P0-3 | LRU cache for text loading | `backend/storage/books.py` |
| P1-1 | Fix N+1 tree queries | `backend/tree/persistence.py` |
| P1-2 | Fix embedding conversion loop | `backend/search/`, `main.py` |
| P1-3 | Background queue for tree writes | `backend/main.py` |
| P1-4 | Fix global cache state | `backend/state.py`, `backend/utils/cache.py` |
| P2-1 | Split utils.py into modules | `backend/search/`, `storage/`, `tree/`, `sync/` | ✅ |
| P2-2 | PostgreSQL as single source | `backend/`, `data/` |
| P2-3 | Search pagination | `backend/main.py`, `frontend/` |
| P2-4 | Fix hardcoded paths | `backend/state.py`, `main.py` |
| P2-5 | Fix logging levels | `backend/main.py` | ✅ |
| P3-1 | Decompose SearchCurate.tsx | `frontend/src/pages/` |
| P3-2 | Add TypeScript API types | `frontend/src/types/` |
| P3-3 | Frontend tree caching | `frontend/src/store.ts` |
