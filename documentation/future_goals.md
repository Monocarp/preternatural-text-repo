# Future Goals: Fine-Tuning LLMs for Pre-Processing

**Created:** 2025-11-27  
**Status:** Planning (target: 50 books milestone)

---

## Overview

This document outlines plans to fine-tune individual LLMs to automate the pre-processing pipeline for extracting stories from historical texts.

### Current Pre-Processing Steps
1. Convert from Word Doc to Markdown
2. Send through indexer
3. Manually split into chunks
4. Send chunks through story extraction
5. Embed chunks and stories

### Target Automation
Fine-tune separate models for:
- **Indexing** — Extract index entries from text
- **Splitting** — Identify story boundaries in continuous text
- **Story Extraction** — Convert raw text to formatted story with metadata

---

## Milestone: 50 Books

Fine-tuning becomes clearly worthwhile at ~50 books (~8,000-10,000 stories).

| Scale | Stories | Viability |
|-------|---------|-----------|
| 15 books | ~2,500 | Minimum viable, may overfit |
| 30 books | ~5,000 | Solid baseline |
| **50 books** | **~8,000-10,000** | **Production quality** |

### Why 50 Books?
1. **Source Diversity** — Different authors, eras, writing styles
2. **Natural Edge Case Coverage** — Enough outliers that model sees them multiple times
3. **Validation Split** — Can hold out 5-10 books entirely for testing

### Pilot Test at 25-30 Books
Before reaching 50, test at ~25-30 books:
- Fine-tune on 20 books
- Test on 5 held-out books
- Measure actual accuracy to see if 50 is needed or diminishing returns hit earlier

---

## Task-Specific Assessment

### Story Extraction (Easiest)
- **Viability:** High
- **Data needed:** 300-500 examples (already have this in `Stories.md` files)
- **Expected accuracy at 50 books:** 85-95%
- **Remaining errors:** Genuinely ambiguous cases

### Splitting / Boundary Detection (Medium)
- **Viability:** Medium → High at scale
- **Challenge:** Requires understanding narrative structure
- **At 50 books:** Thousands of boundary examples across diverse styles
- **Key insight:** Track objective signals (source boundaries) not subjective ones

### Indexing (Medium)
- **Viability:** Medium-High
- **Data needed:** 50 books = 50 different index structures
- **Model learns:** Extract entries regardless of source formatting

---

## Data Quality Guidelines

### What Doesn't Need Standardization

1. **Story Length** — Natural variance is fine (300 chars to 78,000 chars)
   - Source material dictates length, not arbitrary targets
   - Include full variance in training
   - Only exclude extreme outliers (top/bottom 2-3%) if necessary

2. **Page Markers** — Inherently variable based on source
   - Some stories span multiple pages, some don't
   - Overlapping page ranges are valid (multiple short stories on same pages)

3. **Split Decisions** — Based on source structure, not subjective interpretation

### What Should Be Standardized

1. **Title Format** — Pick ONE consistent pattern:
   ```
   Option A: "[Event/Phenomenon] of/at/in [Location/Person]"
   Option B: "[Subject] [Action/Experience] [Key Detail]"
   ```
   Models need consistent examples to learn title generation.

2. **Keywords** (future enhancement) — Should be 3-5 semantic terms, not slugified titles:
   ```json
   // Current (not useful):
   "keywords": ["violent possession and exorcism of peter bernardi of areia"]
   
   // Better:
   "keywords": ["possession", "exorcism", "Italy", "monastery", "16th century"]
   ```

### Split Decision Documentation

Track **objective source signals**, not subjective interpretations:
```json
{
  "split_reason": "author_break" | "new_source" | "chapter_boundary" | "explicit_transition"
}
```

This is objective—either the original text had a break or it didn't.

---

## Data Exclusions for Training

Remove from training batches (keep in production):
- **Overlapping stories** — Edge cases that confuse models
- **Extreme outliers** — Only if clearly anomalous (document why)

**Caution:** Excluding outliers risks the model ignoring similar future stories. Include natural variance where possible.

---

## Resource Estimates

### Compute
- **Minimum:** ~$50-100 (cloud GPU)
- **Ideal:** $200-500 for multiple iterations

### Time Investment
- **Data preparation:** 20-40 hours (major effort)
- **Training/iteration:** 10-20 hours
- **Data prep is 80% of the work**

### Recommended Stack
- **Framework:** [Unsloth](https://github.com/unslothai/unsloth) for 2x faster fine-tuning
- **Base models:** Mistral-7B or Llama-3-8B
- **Method:** QLoRA fine-tuning
- **Platform:** RunPod or Lambda Labs

---

## Timeline

At current pace (~1-2 books/month):
- **25-30 books (pilot test):** ~12-18 months
- **50 books (full fine-tuning):** ~2-4 years

Fine-tuning makes sense at that point because:
1. Mature, consistent conventions established
2. Higher ROI on automation (more future books)
3. Can afford proper held-out evaluation

---

## Summary

| Task | Start Training At | Expected Accuracy |
|------|-------------------|-------------------|
| Story Extraction | 15-20 books | 85-95% |
| Splitting | 30+ books | 70-85% |
| Indexing | 25-30 books | 80-90% |

**Key principle:** Don't fight natural variance. Standardize only what helps learning (titles, keywords). Track objective source signals for splits. Test at 25-30 books before committing to full 50-book fine-tuning.
