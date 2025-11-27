# Data Directory Context

**Last Updated:** 2025-11-26

## Overview

Runtime data files for the search engine and application state. Mix of binary indexes and JSON config.

## File Inventory

| File | Size | Purpose | Readable? |
|------|------|---------|-----------|
| `stories.faiss` | ~2MB | FAISS vector index | ❌ Binary |
| `stories_fts.db` | ~1MB | SQLite FTS5 index | ❌ Binary |
| `stories_metadata.json` | ~200KB | Story metadata backup | ⚠️ Large |
| `codex_tree.json` | ~15KB | Category hierarchy | ✅ Safe |
| `stories_dict.json` | ~300KB | Flat story lookup | ❌ Large |
| `document_store.json` | ~50KB | LEGACY: Haystack embeddings | ❌ Large |
| `documents.json` | ~60KB | LEGACY: Haystack documents | ❌ Large |
| `pending_stories.json` | ~0-1KB | Stories awaiting processing | ✅ Safe |

## DO NOT READ These Files

AI coders should NOT read these files - they waste tokens:

```
❌ stories.faiss          - Binary FAISS index
❌ stories_fts.db         - Binary SQLite database  
❌ document_store.json    - Large embeddings JSON
❌ documents.json         - Large documents JSON
❌ stories_dict.json      - All stories (300KB+)
❌ stories_metadata.json  - Metadata dump (200KB+)
```

## Safe to Read

```
✅ codex_tree.json        - Category structure (~15KB)
✅ pending_stories.json   - Usually empty or small
```

## Data Flow

```
books/{slug}/ source files
       ↓
  backend/ingest_book.py
       ↓
  PostgreSQL (canonical)
       ↓
  backend/search/migrate_haystack_to_direct.py
       ↓
┌──────────────────────────────────────┐
│  data/stories.faiss     (vectors)    │
│  data/stories_fts.db    (text)       │
│  data/stories_metadata.json          │
└──────────────────────────────────────┘
```

## Regenerating Indexes

If indexes are corrupted or you need to rebuild:

```bash
cd backend

# Full reindex from database
python -c "
from search.migrate_haystack_to_direct import migrate
migrate()
"

# Or using the engine directly
python -c "
import os
os.environ['USE_DIRECT_SEARCH'] = 'true'
from search.engine import get_engine
engine = get_engine()
engine.reindex_all()
"
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
