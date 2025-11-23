# Fix: Book Metadata Not Showing in Production

## Problem
Book metadata (title, author, year) was showing locally but not in production (Render).

## Root Cause
1. **Book table was empty in production** - The table existed but had no data
2. **No sync mechanism** - Book metadata from `stories_meta.json` files wasn't being synced to the database
3. **No fallback** - When DB had no books, the cache remained empty

## Solution Implemented

### 1. Auto-Sync Book Metadata from JSON Files (`sync_disk_to_db()`)
Now automatically reads `stories_meta.json` from each book directory and syncs to database:

```python
def sync_disk_to_db():
    # First, sync book metadata from stories_meta.json files
    for book_slug in os.listdir(books_dir):
        meta_path = os.path.join(book_path, "stories_meta.json")
        if os.path.exists(meta_path):
            # Load metadata
            book = Book(
                slug=book_slug,
                title=meta["book_title"],
                author=meta["book_author"],
                year=meta["book_year"]
            )
            db.add(book)
    
    # Then sync stories as before...
```

**When this runs:**
- On server startup
- When `/api/reload-stories` is called

### 2. JSON Fallback for Book Metadata (`preload_book_metadata()`)
If database is unavailable or empty, now loads directly from JSON files:

```python
def preload_book_metadata():
    if not USE_DB:
        # Load from stories_meta.json files
        for book_slug in os.listdir(books_dir):
            meta = json.load("stories_meta.json")
            _book_metadata_cache[book_slug] = {
                "book_title": meta["book_title"],
                "book_author": meta["book_author"],
                "book_year": meta["book_year"]
            }
        return
    
    # Try loading from database
    try:
        books = db.query(Book).all()
        # populate cache...
    except:
        # Fallback to JSON if DB fails
        # Load from stories_meta.json...
```

## How This Fixes Production

### Before Fix
1. Production server starts
2. `sync_disk_to_db()` syncs stories but **NOT book metadata**
3. `preload_book_metadata()` queries empty Book table
4. Book cache is empty `{}`
5. Search returns stories with no book metadata ❌

### After Fix
1. Production server starts
2. `sync_disk_to_db()` **FIRST syncs all books from stories_meta.json**, then syncs stories ✅
3. `preload_book_metadata()` queries populated Book table
4. Book cache is populated with all metadata ✅
5. Search returns stories WITH book metadata ✅

**Fallback protection:** Even if database fails, metadata loads from JSON files

## Files Modified
1. `backend/utils.py`:
   - `sync_disk_to_db()` - Added book metadata sync from JSON files
   - `preload_book_metadata()` - Added JSON fallback logic

## Required File Structure
Each book directory must have `stories_meta.json`:

```json
{
  "book_slug": "christian-mysticism-volume-iv",
  "book_title": "Christian Mysticism Volume IV",
  "book_author": "Joseph Von Gorres",
  "book_year": "1842",
  "extracted_at": "2025-11-23T01:10:41.856846Z",
  "source_files": [...]
}
```

## Deployment Steps

### For Production (Render)
1. **Push changes** to GitHub (triggers Render deploy)
2. **Render will automatically**:
   - Rebuild the container
   - Run startup sequence
   - Sync books from stories_meta.json → database
   - Preload book metadata cache
3. **Verify** - Check logs for:
   ```
   Synced book metadata for 'christian_mysticism_vol_iv': Christian Mysticism Volume IV
   Book metadata sync complete
   Preloaded metadata from database for X books
   ```

### Manual Reload (If Needed)
Call the reload endpoint as an editor:
```bash
POST /api/reload-stories
```

This will re-sync all books and stories.

## Testing Checklist
- [ ] Check production logs for book sync messages
- [ ] Search returns results with book_title, book_author, book_year
- [ ] Archive pages show book metadata
- [ ] Multiple books work correctly
- [ ] Fallback works without database

## Verification Queries

### Check if books are in production DB:
```sql
SELECT slug, title, author, year FROM books;
```

### Check logs for:
- `"Synced book metadata for 'X': Y"` - Confirms sync
- `"Preloaded metadata from database for X books"` - Confirms cache populated
- If you see `"Loaded metadata from JSON files"` - Using fallback (DB issue)

## Rollback Plan
If issues arise:
```bash
git checkout HEAD~1 backend/utils.py
git push
```

Render will auto-deploy the previous version.

## Future Enhancements
1. Add book metadata editing UI
2. Auto-detect new books and sync on file changes
3. Migrate existing production data if needed
