# Colab Preprocessing Pipeline - Block Guide

This folder contains the complete preprocessing pipeline split into 6 Colab code blocks.
Copy each block into a separate Colab cell and run in order.

## Block Overview

| Block | File | Purpose |
|-------|------|---------|
| 1 | `block_1_dependencies.py` | Install packages, load APIs, setup directories |
| 2 | `block_2_story_extraction.py` | GPT-based supernatural story extraction |
| 3 | `block_3_metadata_extraction.py` | Temporal, location, topic extraction functions |
| 4 | `block_4_story_positions.py` | Locate stories in full text + apply metadata |
| 5 | `block_5_chunking.py` | Chunk text with enhanced metadata |
| 6 | `block_6_batch_processor.py` | Main orchestrator - runs full pipeline |

## Setup Requirements

### API Keys (Colab Secrets)
1. **OPENAI_API_KEY** - For GPT story extraction
2. **ANTHROPIC_API_KEY** - For Claude location normalization

To add secrets in Colab:
1. Click the 🔑 key icon in the left sidebar
2. Add `OPENAI_API_KEY` with your OpenAI key
3. Add `ANTHROPIC_API_KEY` with your Anthropic key

### File Uploads
- Upload book folders to `/content/books/`
- Each book folder should contain:
  - `Full_Text.md` - Complete book text with page markers
  - `Stories.md` - Extracted stories (from Block 2)
  - `grouped_index.md` (optional) - Index for metadata

## Workflow Options

### Option A: Full Pipeline (New Book)
1. Run Block 1 (dependencies)
2. Run Block 2 (story extraction) - uncomment `run_story_extraction()`
3. Run Blocks 3-5 (define functions)
4. Run Block 6 - uncomment `batch_preprocess()`

### Option B: Re-index Existing Books
1. Run Block 1 (dependencies)
2. Skip Block 2
3. Run Blocks 3-5 (define functions)
4. Run Block 6 - add book slugs to `force = []` list

## Output Files

The pipeline generates:

| File | Location | Purpose |
|------|----------|---------|
| `story_positions.json` | `books/{slug}/` | Enhanced metadata per story |
| `manual_review.json` | `books/{slug}/` | Stories needing human review |
| `documents.json` | `data/` | All embedded documents |
| `faiss_index.bin` | `data/` | Vector search index |
| `document_store.json` | `data/` | Haystack document store |
| `location_cache.json` | `cache/` | WikiData/Claude location cache |

## Enhanced Metadata Schema

Each story now includes:

```json
{
  "title": "The Loudun Possessions",
  "start_char": 15000,
  "end_char": 18500,
  "pages": "45-52",
  "temporal": {
    "years": [1632, 1633, 1634],
    "centuries": [17],
    "decades": ["1630s"],
    "periods": []
  },
  "locations": {
    "cities": ["Loudun"],
    "regions": ["Poitou"],
    "countries": ["France"]
  },
  "topics": {
    "primary": ["possession", "exorcism", "demonic"],
    "phenomena": ["possession", "exorcism"],
    "entities": ["demonic"],
    "context": ["monastery"]
  },
  "keywords": ["loudun", "possession", "france", "17th century", "exorcism"],
  "confidence": 0.99,
  "status": "AUTO_APPROVED"
}
```

## Confidence Thresholds

- **≥ 0.75**: AUTO_APPROVED (no review needed)
- **< 0.75**: NEEDS_REVIEW (added to manual_review.json)

Confidence calculation:
- 33% temporal (has years OR centuries OR periods)
- 33% locations (has cities OR countries)
- 33% topics (has primary topics)

## Manual Review Process

1. Download `manual_review.json`
2. Open in Notepad++ or similar
3. Review warnings for each flagged story
4. Edit `story_positions.json` to fix issues
5. Change status from "NEEDS_REVIEW" to "REVIEWED"
6. Re-upload and re-run indexing

## Location Normalization

The pipeline uses a hybrid approach:
1. **Cache check** - Previously normalized locations
2. **WikiData API** - Primary lookup for known places
3. **Claude Sonnet 4** - Fallback for obscure/historical names

The cache persists across books (`location_cache.json`), so common locations (France, Rome, etc.) only need to be looked up once.

## Tips

- Run Block 1 first every time (installs packages + loads APIs)
- Block 2 is only needed for NEW book processing
- The `force = []` list in Block 6 lets you reprocess specific books
- Check the printed output for confidence scores and review counts
- The location cache speeds up processing significantly after the first book
