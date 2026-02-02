# Backend Context

**Last Updated:** 2025-11-29

## Quick Overview

FastAPI backend serving the Preternatural Text search and curation system.

## Architecture

```
backend/
├── main.py           # FastAPI app entry point (~180 lines)
├── routes/           # API endpoint modules (NEW - split from main.py)
│   ├── __init__.py   # Router exports
│   ├── dependencies.py # Auth, Pydantic models, shared deps
│   ├── search.py     # /api/search, /api/sources
│   ├── tree.py       # /api/get-tree, category assignment
│   ├── stories.py    # Story CRUD, rendering
│   ├── books.py      # Book listing, full text
│   └── admin.py      # Export, migrations, cleanup
├── models.py         # SQLAlchemy ORM: User, Story, Book, CodexNode, NodeStory
├── state.py          # Centralized app state (AppState singleton)
├── utils_legacy.py   # Backwards-compat shim for old imports
├── ingest_book.py    # CLI script to ingest books into PostgreSQL
├── migrate.py        # Initial migration script for stories/tree
├── migrate_add_books.py  # Migration to add Book table
├── test_model.py     # Embedding model test script
├── search/           # Direct FAISS + SQLite search engine
├── storage/          # Book/story file operations
├── tree/             # Codex tree operations
├── sync/             # Disk ↔ DB synchronization, GitHub sync
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
  ├── routes/ (API routers)
  │   ├── search.py → utils (search_stories)
  │   ├── tree.py → utils (get_cached_tree, assign_to_path)
  │   ├── stories.py → utils (story CRUD functions)
  │   ├── books.py → models, utils (load_full_md)
  │   └── admin.py → utils (sync, export)
  ├── models.py (ORM)
  ├── state.py (app_state)
  └── utils/ (startup imports)

routes/dependencies.py
  ├── models.py (SessionLocal, User)
  └── jwt/PyJWKClient (auth)

search/
  ├── engine.py ← faiss_index.py, fts_index.py
  ├── stories_direct.py ← engine.py
  └── engine_compat.py ← stories_direct.py (wrapper)

state.py
  └── NO DEPENDENCIES (intentionally isolated)
```

## Key Endpoints

### Search Routes (`routes/search.py`)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/search` | POST | No | Hybrid semantic + keyword search |
| `/api/sources` | GET | No | List available book sources |

### Tree Routes (`routes/tree.py`)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/get-tree` | GET | No | Fetch full codex tree |
| `/api/get-stories/{path}` | GET | No | Get stories at tree path |
| `/api/get-unassigned` | GET | No | Get uncategorized stories |
| `/api/assign-category` | POST | Editor | Add story to category |
| `/api/remove-category` | DELETE | Editor | Remove story from category |
| `/api/create-category` | POST | Editor | Create new category/subcategory |
| `/api/delete-category` | DELETE | Editor | Delete category/subcategory |
| `/api/category-info/{path}` | GET | No | Get category metadata |

### Story Routes (`routes/stories.py`)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/render-story` | POST | No | Get story HTML (static or book context) |
| `/api/update-boundaries` | POST | Editor | Edit story char positions |
| `/api/update-title` | POST | Editor | Rename a story |
| `/api/update-keywords` | POST | Editor | Edit story keywords |
| `/api/add-story` | POST | Editor | Create new story + index immediately |
| `/api/delete-story/{title}` | DELETE | Editor | Remove story from all stores |

### Book Routes (`routes/books.py`)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/books` | GET | No | List all books with story counts |
| `/api/books/{slug}` | GET | No | Get book details (optionally with stories) |
| `/api/full-text/{book_slug}` | GET | No | Get book full markdown text |

### Admin Routes (`routes/admin.py`)
| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/export` | POST | No | Export stories to markdown/PDF/Word |
| `/api/migrate-db` | POST | Editor | Recreate DB tables from disk |
| `/api/reload-stories` | POST | Editor | Force reload from disk |
| `/api/cleanup-search-index` | POST | No | Remove orphaned search entries || `/api/rebuild-search-index` | POST | Editor | Rebuild FAISS + FTS5 from stories_dict.json || `/api/full-text/{slug}` | GET | No | Get full book text |

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

---

## Detailed Function Reference

### main.py (~1400 lines)

The FastAPI application entry point with all HTTP endpoints.

#### Startup Functions
| Function | Description | Connects To |
|----------|-------------|-------------|
| `lifespan()` | Context manager for app startup/shutdown. Initializes DB, preloads metadata, syncs disk→DB, initializes search engine | `state.py`, `sync/disk_to_db.py`, `search/` |

#### Authentication
| Function | Description | Connects To |
|----------|-------------|-------------|
| `get_current_user(auth_header)` | Validates JWT from Stack Auth, returns user dict. Uses PyJWKClient for key verification | Stack Auth JWKS |
| `require_editor(user)` | Dependency that ensures user has "editor" role. Auto-provisions new users on first hit | `models.py` |

#### Search Endpoints
| Function | Description | Connects To |
|----------|-------------|-------------|
| `search_api(query, source_filter, search_mode, ...)` | POST `/api/search` - Hybrid/semantic/keyword/exact search with filtering | `search/stories_direct.py` |

#### Tree Endpoints
| Function | Description | Connects To |
|----------|-------------|-------------|
| `get_tree()` | GET `/api/get-tree` - Returns cached codex tree | `utils/cache.py` |
| `assign_category(path, title, ...)` | POST `/api/assign-category` - Add story to category path | `tree/persistence.py`, `sync/github_sync.py` |
| `remove_category(path, title)` | POST `/api/remove-category` - Remove story from category | `tree/persistence.py` |
| `get_stories_at_path_api(path)` | POST `/api/stories-at-path` - Get all stories under a tree path | `sync/disk_to_db.py` |

#### Story CRUD Endpoints
| Function | Description | Connects To |
|----------|-------------|-------------|
| `render_story(title, book_slug, ...)` | POST `/api/render-story` - Get highlighted HTML for a story | `utils/rendering.py` |
| `update_boundaries(book_slug, title, start_char, end_char)` | POST `/api/update-boundaries` - Edit story character positions | `storage/stories.py` |
| `update_title(book_slug, old_title, new_title)` | POST `/api/update-title` - Rename a story across all stores | `storage/stories.py` |
| `update_keywords(book_slug, title, keywords)` | POST `/api/update-keywords` - Edit story keywords | `storage/stories.py` |
| `add_story(book_slug, title, start_char, end_char, ...)` | POST `/api/add-story` - Create new story with embedding | `search/engine.py`, `storage/` |
| `delete_story(title)` | DELETE `/api/delete-story/{title}` - Remove from DB, JSON, search indices | `search/engine.py`, `models.py` |

#### Book Endpoints
| Function | Description | Connects To |
|----------|-------------|-------------|
| `get_books()` | GET `/api/books` - List all books with metadata | `models.py` or JSON fallback |
| `get_book(slug)` | GET `/api/books/{slug}` - Book details + all stories | `storage/books.py` |
| `get_full_text(slug)` | GET `/api/full-text/{slug}` - Full book text | `storage/books.py` |

#### Admin Endpoints
| Function | Description | Connects To |
|----------|-------------|-------------|
| `reload_stories()` | POST `/api/reload-stories` - Re-sync disk → DB | `sync/disk_to_db.py` |
| `export_stories_api(titles, format)` | POST `/api/export` - Export stories as MD/PDF/Word | `utils/export.py` |
| `cleanup_search_index()` | POST `/api/admin/cleanup-search-index` - Remove orphaned entries | `search/engine.py` |

---

### models.py

SQLAlchemy ORM models and database connection setup.

| Model | Description | Relationships |
|-------|-------------|---------------|
| `User` | User with id, email, name, role | None |
| `Book` | Book with slug, title, author, year | `stories` (one-to-many) |
| `Story` | Story with title, book_slug, start_char, end_char, pages, keywords | `book` (many-to-one), `nodes` (many-to-many via NodeStory) |
| `CodexNode` | Category tree node with name, parent_id | `parent`, `children`, `stories` (many-to-many) |
| `NodeStory` | Join table linking CodexNode to Story | `node`, `story` |

---

### state.py

Centralized application state singleton (`AppState` class).

| Attribute | Type | Purpose |
|-----------|------|---------|
| `books_dir` | str | Path to books/ directory |
| `data_dir` | str | Path to data/ directory |
| `USE_DB` | bool | Whether PostgreSQL is available |
| `SessionLocal` | sessionmaker | SQLAlchemy session factory |
| `stories_dict` | dict | {title: story_data} cache |
| `story_positions` | dict | {book_slug: positions} cache |
| `full_mds` | dict | {book_slug: full_text} cache |
| `book_metadata_cache` | dict | {slug: {title, author, year}} |
| `books` | list | List of book slugs |
| `sources` | list | ["All Sources"] + book slugs |
| `book_dir_to_slug` | dict | Maps directory names to slugs |
| `tree_cache` | dict | Cached codex tree |
| `assigned_titles_set` | set | Titles that have category assignments |
| `document_store` | object | Search document store reference |

---

### utils_legacy.py

Backwards-compatibility shim re-exporting from modular structure.

**Purpose:** Allows old code like `from utils_legacy import search_stories` to continue working during transition to `from search import search_stories`.

---

### ingest_book.py

CLI script to ingest books from Stories.md + stories_meta.json into PostgreSQL.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `parse_stories_md(md_path)` | Parse Stories.md to extract story objects from HTML div tags | File I/O |
| `ingest_book(book_slug, dry_run)` | Ingest single book: upsert Book, create/update Story records | `models.py` |
| `ingest_all_books(dry_run)` | Ingest all books with stories_meta.json | `ingest_book()` |

**Usage:** `python ingest_book.py christian_mysticism_vol_iv` or `python ingest_book.py --all`

---

### migrate.py

Initial migration script to populate database from JSON files.

| Function | Description |
|----------|-------------|
| `load_all_stories()` | Load stories from story_positions.json across all books |
| `old_load_codex_tree()` | Load tree from codex_tree.json or initialize from CATEGORIES |
| Main script | Inserts stories, creates CodexNode hierarchy, links NodeStory associations |

---

### migrate_add_books.py

Migration to add Book table and link stories.

| Function | Description |
|----------|-------------|
| `create_books_table()` | CREATE TABLE books with indexes |
| `add_book_id_to_stories()` | ALTER TABLE stories ADD COLUMN book_id |
| `load_books_from_metadata()` | Read stories_meta.json from each book folder |
| `populate_books_table(books_data)` | INSERT books |
| `link_stories_to_books()` | UPDATE story.book_id based on book_slug |
| `verify_migration()` | Verify all stories linked to books |

---

### test_model.py

Simple script to test embedding model loading.

```python
load_model()  # Loads SentenceTransformer from local or HuggingFace
```

---

## search/ Module

### search/__init__.py

Module entry point with feature flag routing.

| Export | Description |
|--------|-------------|
| `USE_DIRECT_SEARCH` | Feature flag: true = FAISS+SQLite, false = Haystack |
| `document_store` | Document store instance |
| `both_pipeline` | Hybrid search pipeline |
| `keyword_pipeline` | BM25-only pipeline |
| `semantic_pipeline` | Embedding-only pipeline |
| `embedder_doc` | Document embedder for indexing |
| `search_stories()` | Main search function |

---

### search/engine.py

Main SearchEngine class combining FAISS + FTS5 + RRF fusion.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `reciprocal_rank_fusion(ranked_lists, weights, k)` | Combine ranked lists using RRF algorithm | Pure function |
| `SearchEngine.__init__(data_dir, model_path, ...)` | Initialize FAISS + FTS5 indices | `faiss_index.py`, `fts_index.py` |
| `SearchEngine.warm_up()` | Pre-load embedding model | SentenceTransformer |
| `SearchEngine.embed_query(query)` | Embed single query text | SentenceTransformer |
| `SearchEngine.embed_documents(texts)` | Batch embed documents | SentenceTransformer |
| `SearchEngine.add_document(doc)` | Add single doc to both indices | FAISS, FTS5 |
| `SearchEngine.add_documents(docs)` | Batch add with auto-embedding | FAISS, FTS5 |
| `SearchEngine.search(query, mode, top_k, ...)` | Main search with mode selection | `_semantic_search`, `_exact_search`, `_rerank` |
| `SearchEngine._semantic_search(query, top_k, filter_fn)` | FAISS vector similarity | `faiss_index.py` |
| `SearchEngine._exact_search(query, top_k, ...)` | FTS5 phrase match | `fts_index.py` |
| `SearchEngine._rerank(query, ranked_results)` | Cross-encoder reranking | CrossEncoder |
| `SearchEngine.delete_document(doc_id)` | Remove from both indices | FAISS, FTS5 |
| `SearchEngine.delete_by_title(title)` | Delete all docs with title | FAISS, FTS5 |
| `SearchEngine.cleanup_orphaned_entries(valid_titles)` | Remove entries not in valid set | Used on startup |
| `init_search_engine(data_dir, model_path, ...)` | Initialize global engine instance | Global `_search_engine` |
| `get_search_engine()` | Get global engine instance | Used everywhere |

---

### search/faiss_index.py

FAISS index management for vector similarity search.

| Function | Description |
|----------|-------------|
| `FAISSIndexManager.__init__(dimension)` | Initialize with dimension (1024 for bge-large) |
| `FAISSIndexManager.create_index()` | Create IndexFlatIP for cosine similarity |
| `FAISSIndexManager.add_documents(doc_ids, embeddings, metadata_list)` | Add vectors to FAISS + update ID map |
| `FAISSIndexManager.search(query_embedding, top_k, filter_fn)` | K-NN search with optional filtering |
| `FAISSIndexManager.remove_documents(doc_ids)` | Remove by rebuilding index |
| `FAISSIndexManager.save(index_path)` | Save FAISS index + mapping JSON |
| `FAISSIndexManager.load(index_path)` | Load FAISS index + mapping JSON |
| `FAISSIndexManager.get_metadata(doc_id)` | Get metadata for document |

---

### search/fts_index.py

SQLite FTS5 full-text search index.

| Function | Description |
|----------|-------------|
| `FTS5Index.__init__(db_path)` | Initialize SQLite DB with FTS5 tables |
| `FTS5Index.add_document(doc_id, title, content, ...)` | Add single document |
| `FTS5Index.add_documents_batch(documents)` | Batch add documents |
| `FTS5Index.search(query, top_k, book_filter)` | BM25 search with optional filter |
| `FTS5Index.delete_document(doc_id)` | Delete by doc_id |
| `FTS5Index.delete_by_title(title)` | Delete all with matching title |
| `FTS5Index.delete_by_book(book_slug)` | Delete all for a book |
| `FTS5Index.get_content(doc_id)` | Get document content for reranking |
| `FTS5Index.get_contents_batch(doc_ids)` | Batch get contents |
| `FTS5Index.get_metadata(doc_id)` | Get document metadata |
| `FTS5Index.get_all_titles()` | Get all unique titles |

---

### search/models.py

Data models for search engine.

| Class | Description |
|-------|-------------|
| `StoryDocument` | Dataclass with id, content, meta, embedding, score |
| `StoryDocument.from_haystack_doc(doc)` | Convert from Haystack Document |

---

### search/stories_direct.py

Main search function using Direct engine.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `search_stories(query, source_filter, search_mode, ...)` | Search with enrichment + filtering | `engine.py`, `utils/cache.py` |

---

### search/engine_compat.py

Compatibility layer for Haystack→Direct transition.

| Class | Description |
|-------|-------------|
| `DocumentStoreCompat` | Mimics InMemoryDocumentStore API |
| `PipelineCompat` | Mimics Haystack Pipeline.run() |
| `DocumentEmbedderCompat` | Mimics SentenceTransformersDocumentEmbedder |

| Function | Description |
|----------|-------------|
| `initialize_search_engine()` | Initialize engine + create compat wrappers |
| `get_document_store()` | Get DocumentStoreCompat |
| `get_both_pipeline()` | Get hybrid PipelineCompat |

---

### search/pipelines.py (Legacy Haystack)

Original Haystack pipeline initialization (used when `USE_DIRECT_SEARCH=false`).

| Export | Description |
|--------|-------------|
| `document_store` | InMemoryDocumentStore loaded from JSON |
| `both_pipeline` | Hybrid pipeline with DocumentJoiner |
| `keyword_pipeline` | BM25-only pipeline |
| `semantic_pipeline` | Embedding-only pipeline |
| `embedder_doc` | SentenceTransformersDocumentEmbedder |

---

### search/stories.py (Legacy Haystack)

Search function using Haystack (used when `USE_DIRECT_SEARCH=false`).

| Function | Description |
|----------|-------------|
| `search_stories(query, source_filter, search_mode, ...)` | Run Haystack pipelines + enrich results |

---

## storage/ Module

### storage/__init__.py

Re-exports from submodules.

---

### storage/books.py

Book file I/O operations.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `load_full_md(book_slug)` | Load Full_Text.md with LRU cache (10 books) | File I/O |
| `clear_full_md_cache()` | Clear the LRU cache | Cache |
| `load_story_positions(book_slug)` | Load story_positions.json with caching | `state.py` |
| `save_story_positions(book_slug)` | Save story_positions.json | File I/O |

---

### storage/stories.py

Story update operations.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `update_story_boundaries(book_slug, title, start_char, end_char)` | Update positions in JSON + DB + cache | `books.py`, `models.py`, `sync/github_sync.py` |
| `update_story_title(book_slug, old_title, new_title)` | Rename across all stores | `tree/`, `models.py`, search indices |
| `update_story_keywords(book_slug, title, keywords)` | Update keywords everywhere | JSON, DB, search metadata |
| `_update_document_store_metadata(old_title, new_title)` | Update search index metadata | FAISS/Haystack |

---

### storage/pending.py

Pending stories queue management.

| Function | Description |
|----------|-------------|
| `load_pending_stories()` | Load pending_stories.json |
| `save_pending_stories(pending_stories)` | Save pending_stories.json |
| `check_story_overlap(book_slug, new_start, new_end, exclude_title)` | Check if range overlaps existing stories |

---

## tree/ Module

### tree/__init__.py

Re-exports from submodules.

---

### tree/operations.py

Pure tree manipulation functions (no I/O).

| Constant | Description |
|----------|-------------|
| `CATEGORIES` | Default category structure (nested dict) |

| Function | Description |
|----------|-------------|
| `merge_trees(existing_tree, new_tree)` | Recursively merge two trees preserving stories |
| `assign_to_path(tree, path, story, stories_dict)` | Add story title to path in tree |
| `remove_from_path(tree, path, title)` | Remove story from path |
| `find_paths_for_title(tree, title)` | Find all paths containing a title |

---

### tree/persistence.py

Tree loading/saving with DB and JSON.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `load_codex_tree_from_json()` | Load from codex_tree.json or create default | File I/O |
| `save_codex_tree_to_json(tree)` | Save to codex_tree.json | File I/O |
| `insert_recursive(tree_json, db, parent_id)` | Insert tree nodes into database | `models.py` |
| `load_codex_tree()` | Load from DB with JSON fallback, builds tree structure | DB + JSON |
| `save_codex_tree(tree)` | Save to JSON + DB + optional HuggingFace/GitHub | DB, JSON, GitHub |

---

### tree/queries.py

Tree query utilities.

| Function | Description |
|----------|-------------|
| `get_stories_for_subcats(tree, path_parts, subcat_names)` | Get stories from multiple subcategories |
| `_collect_stories_recursive(node, stories_set)` | Helper to walk tree collecting stories |

---

## sync/ Module

### sync/__init__.py

Re-exports from submodules.

---

### sync/disk_to_db.py

Disk to database synchronization.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `cleanup_orphaned_node_stories(db)` | Remove NodeStory entries with invalid story_ids | DB |
| `load_all_stories()` | Load all stories from story_positions.json files | `storage/books.py` |
| `enrich_stories_with_book_metadata(stories)` | Add book_title, author, year to story dicts | `state.py` cache |
| `get_stories_at_path(tree, path)` | Get stories at tree path, enriched | `state.py` |
| `sync_books_from_metadata(db)` | Upsert Book records from stories_meta.json | DB |
| `sync_disk_to_db()` | Full sync: disk → memory → DB. Called on startup | Everything |

---

### sync/github_sync.py

GitHub repository synchronization.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `get_github_config()` | Get token, repo, branch from env | Environment |
| `get_file_sha(file_path)` | Get current SHA for file updates | GitHub API |
| `sync_file_to_github(local_path, repo_path, commit_message)` | PUT file content via GitHub API | GitHub API |
| `sync_codex_tree(reason)` | Sync codex_tree.json | `sync_file_to_github` |
| `sync_stories_dict(reason)` | Sync stories_dict.json | `sync_file_to_github` |
| `sync_document_store(reason)` | Sync document_store.json | `sync_file_to_github` |
| `sync_story_positions(book_slug, reason)` | Sync book's story_positions.json | `sync_file_to_github` |
| `sync_all_changed_files(book_slugs, include_tree, ...)` | Batch sync multiple files | Multiple syncs |
| `on_story_boundary_change(book_slug, title)` | Auto-sync after boundary update | Called from storage |
| `on_story_title_change(book_slug, old_title, new_title)` | Auto-sync after rename | Called from storage |
| `on_story_added(book_slug, title)` | Auto-sync after adding story | Called from main.py |
| `on_story_deleted(book_slug, title)` | Auto-sync after deletion | Called from main.py |
| `on_category_change(action, title, path)` | Auto-sync after category change | Called from main.py |

---

## utils/ Module

### utils/__init__.py

Re-exports from all submodules + utils_legacy.

---

### utils/cache.py

Caching utilities.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `invalidate_cache()` | Mark caches as stale, clear assigned_titles | `state.py` |
| `get_cached_tree()` | Get tree, reload if invalidated | `tree/persistence.py` |
| `get_book_metadata(book_slug)` | Get book metadata from cache or DB | `state.py`, DB |
| `clear_book_metadata_cache()` | Clear book metadata cache | `state.py` |
| `preload_book_metadata()` | Load all book metadata at startup | DB or JSON fallback |
| `get_assigned_titles_set()` | Get set of titles with category assignments | Cache or rebuild |
| `rebuild_assigned_titles_cache()` | Walk tree to build assigned titles set | `get_cached_tree()` |
| `clear_assigned_titles_cache()` | Clear assigned titles cache | `state.py` |

---

### utils/rendering.py

Story rendering utilities.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `render_md_with_scroll_and_highlight(book_slug, start_char, end_char, page, search_query)` | Generate HTML with story highlighted + page anchors | `storage/books.py` |
| `render_static_story(story)` | Get plain story text from full_md | `storage/books.py` |
| `find_book_slug(title)` | Find which book contains a story title | `storage/books.py` |

---

### utils/export.py

Export utilities.

| Function | Description | Connects To |
|----------|-------------|-------------|
| `export_stories(stories, format, is_single)` | Export to MD, PDF, or Word | pandoc, reportlab, python-docx |
| `export_updated_jsons(pending_updates)` | Export updated story_positions.json as ZIP | zipfile |

---

### utils/storage.py

Re-exports storage functions from utils_legacy for backwards compat.

---

### utils/tree_ops.py

Re-exports tree operations from tree/operations.py with duplicate CATEGORIES.

---

## Data Flow Diagrams

### Search Request Flow
```
Client POST /api/search
    ↓
main.py search_api()
    ↓
search/stories_direct.py search_stories()
    ↓
search/engine.py SearchEngine.search()
    ├── FAISS semantic search
    ├── FTS5 keyword search
    └── RRF fusion
    ↓
Enriched results + book metadata
    ↓
JSON response
```

### Story Update Flow
```
Client POST /api/update-boundaries
    ↓
main.py update_boundaries() [requires editor]
    ↓
storage/stories.py update_story_boundaries()
    ├── Update story_positions cache
    ├── Save story_positions.json
    ├── Update DB story record
    ├── Invalidate caches
    └── Trigger GitHub sync
    ↓
JSON response
```

### Startup Flow
```
main.py lifespan()
    ├── Test database connection
    ├── preload_book_metadata()
    ├── sync_disk_to_db()
    │   ├── Load all story_positions.json
    │   ├── Update stories_dict
    │   ├── Sync to PostgreSQL
    │   └── Delete orphaned DB stories
    ├── load_codex_tree()
    └── Initialize search engine
        ├── Load FAISS index
        ├── Load FTS5 database
        └── Cleanup orphaned entries
```
