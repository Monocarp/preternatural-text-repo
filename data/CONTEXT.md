# Data Directory Context

**Last Updated:** 2025-11-29

## Overview

Runtime data files for the search engine and application state. Mix of binary indexes and JSON config.

## Two Search Paths

The backend supports **two parallel search implementations**:

1. **Haystack Path** (legacy): Set `USE_DIRECT_SEARCH=false`
   - Uses: `document_store.json`, `documents.json`, `faiss_index.bin`
   
2. **Direct Path** (recommended): Set `USE_DIRECT_SEARCH=true`
   - Uses: `stories.faiss`, `stories.faiss.map.json`, `stories_fts.db`

## File Inventory

| File | Size | Purpose | Readable? |
|------|------|---------|-----------|
| **Direct Search Files** |
| `stories.faiss` | ~2MB | FAISS vector index (IndexFlatIP) | ❌ Binary |
| `stories.faiss.map.json` | ~200KB | ID map + metadata for FAISS | ❌ Large |
| `stories_fts.db` | ~1MB | SQLite FTS5 index | ❌ Binary |
| **Haystack Files (from Colab)** |
| `document_store.json` | ~50MB | Haystack InMemoryDocumentStore | ❌ Large |
| `documents.json` | ~60MB | Documents with embeddings | ❌ Large |
| `faiss_index.bin` | ~2MB | Haystack FAISS index (L2) | ❌ Binary |
| **Shared Files** |
| `codex_tree.json` | ~15KB | Category hierarchy | ✅ Safe |
| `stories_dict.json` | ~300KB | Flat story lookup by title | ❌ Large |
| `pending_stories.json` | ~0-1KB | Stories awaiting processing | ✅ Safe |

## DO NOT READ These Files

AI coders should NOT read these files - they waste tokens:

```
❌ stories.faiss          - Binary FAISS index
❌ stories.faiss.map.json - Large JSON with all metadata
❌ stories_fts.db         - Binary SQLite database  
❌ document_store.json    - Large Haystack store (~50MB)
❌ documents.json         - Large documents (~60MB)
❌ faiss_index.bin        - Binary Haystack FAISS
❌ stories_dict.json      - All stories (300KB+)
```

## Safe to Read

```
✅ codex_tree.json        - Category structure (~15KB)
✅ pending_stories.json   - Usually empty or small
```

## Adding a New Book - Complete Workflow

### Step 1: Upload to Colab
For each book, upload to `/content/books/{book_slug}/`:
- `Full_Text.md` - Complete book text with page markers
- `Stories.md` - Extracted stories with HTML formatting
- `grouped_index.md` - Index entries with page numbers

### Step 2: Run Pre-Processing/Step 3.txt
The Colab script uses **Haystack** and produces:
- `documents.json` - All docs with embeddings
- `faiss_index.bin` - FAISS L2 index  
- `document_store.json` - Haystack InMemoryDocumentStore
- `story_positions.json` - Character positions (per book)

### Step 3: Download Files
- Place Haystack files (`documents.json`, `faiss_index.bin`, `document_store.json`) in `data/`
- Place `story_positions.json` in `books/{slug}/`

### Step 4: Migrate to Direct Format (if using direct search)
```bash
cd backend
python -m search.migrate_haystack_to_direct --input ../data/document_store.json --output ../data/
```

This creates:
- `stories.faiss` - FAISS IndexFlatIP (cosine similarity via normalized vectors)
- `stories.faiss.map.json` - Contains `{id_map: [], metadata: {}, dimension: 1024}`
- `stories_fts.db` - SQLite FTS5 for BM25 keyword search

### Step 5: Ingest Book into Database ⚠️ REQUIRED

**This step is essential!** Without it, the book will appear in Story Archive (which reads from `books/` folder) but NOT in Book Archive (which reads from PostgreSQL).

```bash
cd backend
python ingest_book.py {book_slug}

# Example:
python ingest_book.py operation_trojan_horse

# To preview without committing:
python ingest_book.py {book_slug} --dry-run

# To ingest all books with stories_meta.json:
python ingest_book.py --all
```

The ingest script reads from `books/{slug}/`:
- `stories_meta.json` - Book metadata (title, author, year)
- `Stories.md` - Parsed for story content
- `story_positions.json` - Character positions

And creates/updates in PostgreSQL:
- `Book` record with slug, title, author, year
- `Story` records linked to the book

### Why Both Archives Need Different Data Sources

| Archive | Data Source | Populated By |
|---------|-------------|--------------|
| Story Archive (`/api/sources`) | `books/` folder scan | Placing files in `books/{slug}/` |
| Book Archive (`/api/books`) | PostgreSQL database | Running `ingest_book.py` |

**If a book appears in Story Archive but not Book Archive**, run `ingest_book.py`.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    COLAB PREPROCESSING                          │
│  books/{slug}/Full_Text.md + Stories.md + grouped_index.md      │
│                          ↓                                      │
│              Pre-Processing/Step 3.txt                          │
│                          ↓                                      │
│  documents.json + faiss_index.bin + document_store.json         │
└─────────────────────────────────────────────────────────────────┘
                           ↓ download
┌─────────────────────────────────────────────────────────────────┐
│                       data/ FOLDER                              │
│                                                                 │
│  Haystack files:                  Direct files (after migrate): │
│  ├── document_store.json    ──►   ├── stories.faiss             │
│  ├── documents.json               ├── stories.faiss.map.json    │
│  └── faiss_index.bin              └── stories_fts.db            │
│                                                                 │
│  Shared files:                                                  │
│  ├── codex_tree.json        (category assignments)              │
│  ├── stories_dict.json      (story lookup cache)                │
│  └── pending_stories.json   (processing queue)                  │
└─────────────────────────────────────────────────────────────────┘
```

## Running the Backend

```bash
cd backend

# Haystack path (uses document_store.json)
$env:USE_DIRECT_SEARCH='false'
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Direct path (uses stories.faiss + stories_fts.db)
$env:USE_DIRECT_SEARCH='true'
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Regenerating Direct Indexes

If direct indexes are corrupted or need rebuild from Haystack files:

```bash
cd backend
python -m search.migrate_haystack_to_direct --input ../data/document_store.json --output ../data/
```

## Codex Tree Structure

`codex_tree.json` is hierarchical:
```json
{
  "Demonic Activity": {
    "Possession": {
      "_stories": ["Story Title 1", "Story Title 2"]
    },
    "Exorcism": {
      "_stories": ["Story Title 3"]
    }
  },
  "Ghostly Activity": {
    "_stories": ["Story Title 4"]
  }
}
```

**Key:** `_stories` arrays contain story titles assigned to that node.

## Backup Strategy

- **PostgreSQL:** Primary backup via Neon
- **JSON files:** Committed to git (secondary backup)
- **FAISS/FTS5:** Regeneratable from DB; not backed up

## Invariants

1. **PostgreSQL is source of truth** for stories, books, categories
2. **JSON files are read caches** - regenerated from DB on mutations
3. **FAISS index must match DB** - reindex if stories added/removed
4. **Embeddings are model-specific** - changing model requires full reindex
