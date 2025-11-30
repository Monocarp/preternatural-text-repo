# Search Module Context

**Last Updated:** 2025-11-29

## Overview

Hybrid search engine using Direct FAISS + SQLite FTS5. Migrated from Haystack InMemoryDocumentStore for better scalability.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  DirectSearchEngine                      │
│                    (engine.py)                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐     ┌─────────────────────────┐   │
│  │   FAISSIndex    │     │      FTSIndex           │   │
│  │ (faiss_index.py)│     │   (fts_index.py)        │   │
│  │                 │     │                         │   │
│  │ - IndexFlatIP   │     │ - SQLite FTS5           │   │
│  │ - 1024-dim vecs │     │ - BM25 ranking          │   │
│  │ - Cosine sim    │     │ - Porter stemmer        │   │
│  └─────────────────┘     └─────────────────────────┘   │
│                    ↓                 ↓                  │
│              ┌─────────────────────────────┐            │
│              │   Reciprocal Rank Fusion    │            │
│              │    (RRF, k=60)              │            │
│              └─────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `engine.py` | Main search engine | `DirectSearchEngine`, `search()` |
| `faiss_index.py` | Vector index | `FAISSIndex`, `search()`, `add()` |
| `fts_index.py` | Full-text index | `FTSIndex`, `search()`, `add()` |
| `stories_direct.py` | Story search API | `search_stories()` |
| `engine_compat.py` | Haystack compatibility | `search_stories()` wrapper |
| `models.py` | Data models | `SearchResult`, `SearchMode` |

## Critical Architectural Decisions

### 1. Lazy Model Loading
```python
# engine.py - SentenceTransformer loaded on first use, not import
@property
def embedder(self):
    if self._embedder is None:
        from sentence_transformers import SentenceTransformer
        self._embedder = SentenceTransformer(self.model_name)
    return self._embedder
```
**Why:** Reduces startup from 11.5s to 0.7s. Don't change this without considering cold-start impact.

### 2. Normalized Embeddings
```python
# Vectors are L2-normalized for cosine similarity via inner product
embedding = embedding / np.linalg.norm(embedding)
```
**Invariant:** All vectors in FAISS index MUST be normalized. FAISS IndexFlatIP computes inner product, which equals cosine similarity only for unit vectors.

### 3. RRF Score Fusion
```python
# Reciprocal Rank Fusion combines FAISS and FTS5 results
rrf_score = 1 / (k + rank_semantic) + 1 / (k + rank_keyword)
```
**Why:** RRF is robust to score scale differences between systems. Don't switch to simple score averaging.

### 4. Score Thresholds by Mode
```python
SCORE_THRESHOLDS = {
    'hybrid': 0.0001,   # RRF scores are small (~0.01-0.03)
    'semantic': 0.01,   # Cosine similarity
    'keyword': 0.0,     # BM25 scores vary widely
    'exact': 0          # Binary match
}
```
**Why:** Each mode produces different score scales. A single threshold doesn't work.

## Search Modes

| Mode | Implementation | Score Range | Use Case |
|------|---------------|-------------|----------|
| `HYBRID` | FAISS + FTS5 + RRF | 0.001 - 0.05 | Default, best quality |
| `SEMANTIC` | FAISS only | 0.0 - 1.0 | Conceptual similarity |
| `KEYWORD` | FTS5 only | 0.0 - 50+ | Exact term matching |
| `EXACT` | Substring search | 0 or 1 | Literal text search |

## Usage

```python
from search.stories_direct import search_stories

results = search_stories(
    query="demon possession",
    search_mode="Both",     # Maps to HYBRID
    top_k=50,
    source_filter="All Sources"
)
# Returns: [{title, book_slug, content, score, pages, keywords}, ...]
```

## Feature Flags

| Flag | Default | Effect |
|------|---------|--------|
| `USE_DIRECT_SEARCH` | `true` | Use this engine (vs legacy Haystack) |
| `ENABLE_RERANKER` | `false` | Cross-encoder reranking (adds ~200ms latency) |

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Cold start | ~0.7s | Lazy model load |
| Warm search | ~0.14s | After first query |
| Index size | ~3MB | 925 stories |
| Memory | ~500MB | With model loaded |

## Data Files

| File | Purpose | Regenerate With |
|------|---------|-----------------|
| `data/stories.faiss` | Vector index | `engine.reindex_all()` |
| `data/stories_fts.db` | FTS5 database | `engine.reindex_all()` |
| `data/stories_metadata.json` | Metadata backup | `engine.save()` |

## Extending the Search Engine

### Adding a new search mode:
1. Add enum value to `SearchMode` in `models.py`
2. Add threshold to `SCORE_THRESHOLDS` in `stories_direct.py`
3. Implement in `DirectSearchEngine.search()` in `engine.py`

### Adding a new field to index:
1. Update `FAISSIndex.add()` and `FTSIndex.add()` 
2. Update metadata schema in `engine.py`
3. Run `migrate_haystack_to_direct.py` to reindex

### Changing embedding model:
1. Update `model_name` in `DirectSearchEngine.__init__()`
2. Delete `data/stories.faiss` (dimension may change)
3. Run full reindex

## Legacy Files (Still Work, But Deprecated)

| File | Status | Removal Plan |
|------|--------|--------------|
| `pipelines.py` | Works if `USE_DIRECT_SEARCH=false` | Remove when confident |
| `stories.py` | Haystack search_stories | Remove with pipelines.py |

## Common Issues

**Issue:** Search returns 0 results  
**Cause:** Score threshold filtering out RRF scores  
**Fix:** Check `SCORE_THRESHOLDS` matches search mode

**Issue:** Slow first search (~10s)  
**Cause:** SentenceTransformer model loading  
**Fix:** This is expected; subsequent searches are fast


