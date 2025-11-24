# Immediate Indexing Changes - Implementation Guide

## Summary
This document contains all changes needed to switch from pending queue to immediate indexing for the add-story feature.

## Backend Changes Completed

### ✅ COMPLETED: `backend/utils.py`
- Added `embedder_doc` for immediate story embedding
- `check_story_overlap` function already exists
- `load_pending_stories` and `save_pending_stories` exist but will be removed after frontend changes

## Backend Changes Still Needed

### File: `backend/main.py`

#### CHANGE 1: Replace `/api/add-story` endpoint

Find the existing `@app.post("/api/add-story")` function (around line 750-850) and replace the ENTIRE function with the version in the appendix below.

Key changes:
- Step 10 now does IMMEDIATE INDEXING instead of adding to pending queue
- Removed references to `pending_count` in return value
- Changed success message to "saved and indexed successfully"

#### CHANGE 2: Delete `/api/pending-stories-count` endpoint

Find and delete this entire endpoint:
```python
@app.get("/api/pending-stories-count")
def get_pending_stories_count():
    ...
```

#### CHANGE 3: Delete `/api/reindex-pending` endpoint

Find and delete this entire endpoint:
```python
@app.post("/api/reindex-pending")
def reindex_pending_stories(user = Depends(require_editor)):
    ...
```

## Frontend Changes Needed

### File 1: `frontend/src/components/PendingStoriesBadge.tsx`
**ACTION**: Delete this entire file

### File 2: Navigation component (find where badge was added)
**ACTION**: Remove these lines:
```typescript
import PendingStoriesBadge from './PendingStoriesBadge'
<PendingStoriesBadge />
```

### File 3: `frontend/src/pages/SearchCurate.tsx`

Find the `handleSaveNewStory` function and make these changes:

**OLD**:
```typescript
alert(`Story "${newStoryTitle}" saved successfully! ${retryResponse.data.pending_count} stories pending reindex.`)
```

**NEW**:
```typescript
alert(`Story "${newStoryTitle}" saved and indexed successfully! It is now searchable.`)
```

**OLD**:
```typescript
alert(`Story "${newStoryTitle}" saved successfully! ${response.data.pending_count} stories pending reindex.`)
```

**NEW**:
```typescript
alert(`Story "${newStoryTitle}" saved and indexed successfully! It is now searchable.`)
```

### File 4: Archive page (wherever new story feature was added)
Make the same alert message changes as in SearchCurate.tsx

## Cleanup

### File to delete:
- `data/pending_stories.json` (if it exists)

### Functions to remove from `backend/utils.py` (after testing):
- `load_pending_stories()`
- `save_pending_stories(pending_stories)`

---

## APPENDIX: New /api/add-story Endpoint Code

```python
# ------------------- ADD STORY (IMMEDIATE INDEXING) ------------------- #
@app.post("/api/add-story")
def add_story(body: AddStoryBody, user = Depends(require_editor)):
    """
    Add a new story to a book and immediately index it for search.
    Story is searchable as soon as this endpoint returns.
    """
    try:
        # 1. Validate book exists
        book_path = os.path.join(BOOKS_DIR, body.book_slug)
        if not os.path.isdir(book_path):
            raise HTTPException(404, f"Book not found: {body.book_slug}")
        
        # 2. Load full text to validate positions
        from utils import load_full_md
        full_md = load_full_md(body.book_slug)
        if not full_md:
            raise HTTPException(404, f"Full_Text.md not found for {body.book_slug}")
        
        # 3. Validate positions
        if body.start_char < 0 or body.end_char > len(full_md):
            raise HTTPException(400, f"Character positions out of bounds (0-{len(full_md)})")
        
        if body.end_char <= body.start_char:
            raise HTTPException(400, "end_char must be greater than start_char")
        
        # 4. Extract and validate story text
        story_text = full_md[body.start_char:body.end_char].strip()
        if not story_text:
            raise HTTPException(400, "Story text is empty")
        
        if len(story_text) < 50:
            raise HTTPException(400, f"Story too short ({len(story_text)} chars). Minimum 50 characters.")
        
        # 5. Check for duplicate title
        from utils import load_story_positions
        positions = load_story_positions(body.book_slug)
        if body.title in positions:
            raise HTTPException(400, f"Story title '{body.title}' already exists in {body.book_slug}")
        
        # 6. Check for overlaps
        from utils import check_story_overlap
        has_overlap, overlaps = check_story_overlap(body.book_slug, body.start_char, body.end_char)
        
        log.info(f"Overlap check: has_overlap={has_overlap}, force_overlap={body.force_overlap}, overlaps={len(overlaps) if has_overlap else 0}")
        
        if has_overlap and not body.force_overlap:
            # Return overlap warning, require confirmation
            log.info(f"Returning overlap warning for '{body.title}': {overlaps}")
            return {
                "status": "overlap_warning",
                "message": "Story overlaps with existing stories",
                "overlaps": overlaps,
                "requires_confirmation": True
            }
        
        # 7. Parse keywords
        keywords_list = [k.strip() for k in body.keywords.split(",") if k.strip()]
        
        # 8. Update story_positions.json
        positions[body.title] = {
            "start_char": body.start_char,
            "end_char": body.end_char,
            "pages": body.pages,
            "keywords": keywords_list
        }
        from utils import story_positions, save_story_positions
        story_positions[body.book_slug] = positions
        save_success = save_story_positions(body.book_slug)
        
        if not save_success:
            raise HTTPException(500, "Failed to save story_positions.json")
        
        log.info(f"Saved story '{body.title}' to story_positions.json")
        
        # 9. Add to database (if enabled)
        from utils import USE_DB, SessionLocal
        if USE_DB and SessionLocal:
            try:
                with SessionLocal() as db:
                    from models import Story, Book
                    
                    book = db.query(Book).filter_by(slug=body.book_slug).first()
                    if book:
                        story = Story(
                            title=body.title,
                            book_id=book.id,
                            book_slug=body.book_slug,
                            pages=body.pages,
                            keywords=",".join(keywords_list),
                            start_char=body.start_char,
                            end_char=body.end_char
                        )
                        db.add(story)
                        db.commit()
                        log.info(f"Added story '{body.title}' to database")
            except Exception as e:
                log.error(f"Failed to add story to database: {e}")
                # Don't fail the entire operation if DB fails
        
        # 10. IMMEDIATE INDEXING: Embed the story right now
        log.info(f"Embedding story '{body.title}' immediately...")
        from haystack import Document
        from utils import embedder_doc, document_store, document_store_path
        import numpy as np
        
        story_doc = Document(
            content=story_text,
            meta={
                "type": "story",
                "title": body.title,
                "book": body.book_slug,
                "source": body.book_slug.replace('_', ' '),
                "pages": body.pages,
                "keywords": ", ".join(keywords_list),
                "start_char": body.start_char,
                "end_char": body.end_char
            }
        )
        
        # Embed the story
        result = embedder_doc.run([story_doc])
        embedded_doc = result["documents"][0]
        
        # Convert embedding to list for JSON serialization
        if embedded_doc.embedding is not None and isinstance(embedded_doc.embedding, np.ndarray):
            embedded_doc.embedding = embedded_doc.embedding.tolist()
        
        # Add to document store
        document_store.write_documents([embedded_doc])
        
        # Convert ALL embeddings to lists before saving
        all_docs = list(document_store.filter_documents({}))
        for doc in all_docs:
            if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                doc.embedding = doc.embedding.tolist()
        
        document_store.save_to_disk(document_store_path)
        
        log.info(f"Story '{body.title}' embedded and added to document store")
        
        # 11. Invalidate cache
        from utils import invalidate_cache
        invalidate_cache()
        
        log.info(f"Story '{body.title}' added to {body.book_slug} by {user.get('email')} and is now searchable!")
        
        return {
            "status": "success",
            "message": f"Story '{body.title}' saved and indexed successfully. It is now searchable!",
            "story": {
                "title": body.title,
                "book_slug": body.book_slug,
                "pages": body.pages,
                "start_char": body.start_char,
                "end_char": body.end_char,
                "length": len(story_text),
                "indexed": True
            },
            "overlap_warnings": [f"{o['title']} ({o['overlap_percent']}% overlap)" for o in overlaps] if has_overlap else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to add story: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to add story: {str(e)}")
```

## Testing Checklist

After all changes:
- [ ] Add a new story - should take 2-5 seconds
- [ ] Check success message - should say "indexed successfully"
- [ ] Search for new story immediately - should be found
- [ ] No pending badge should appear in navigation
- [ ] Backend logs should show "Story X is now searchable!"
