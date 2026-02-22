# Adding New Books to the Lexicon

**Last Updated:** 2026-02-21

This document provides step-by-step instructions for adding a new book to the Preternatural Text Repository. Following these steps will ensure the book integrates properly with the search system, database, and user interface.

---

## Prerequisites

Before adding a book, you must have these files prepared (typically from pre-processing):

1. **`Full_Text.md`** - Complete book text with `[Page X]` markers
2. **`story_positions.json`** - Story metadata with character positions
3. **`stories_meta.json`** - Book metadata (title, author, year, etc.)
4. **`Stories.md`** - (Optional) Extracted stories for reference

---

## Step 1: Create Book Directory

Create a new folder in `books/` with a **short, lowercase, underscore-separated name**:

```
books/
└── your_book_name/          ← Use underscores, keep it short
    ├── Full_Text.md
    ├── story_positions.json
    ├── stories_meta.json
    └── Stories.md (optional)
```

**Naming Convention:**
- ✅ Good: `the_terror_that_comes_at_night`
- ❌ Bad: `the-terror-that-comes-in-the-night-an-experience-centered-study-of-supernatural-assault-traditions`
- ❌ Bad: `The Terror That Comes at Night` (no spaces, no capitals)

---

## Step 2: Fix Book Slug in stories_meta.json

**CRITICAL:** The `book_slug` field in `stories_meta.json` **MUST match the directory name exactly**.

> **⚠️ This has caused issues with EVERY book added so far.** Pre-processing scripts generate long slugs with hyphens (e.g., `the-terror-that-comes-in-the-night-an-experience-centered-study`). These MUST be changed to match the directory name (short, underscored). If they don't match, the **source filter in Search & Curate will return 0 results** for that book because the backend maps directory → slug via this field, and the search index stores the directory name.

Open `books/your_book_name/stories_meta.json` and verify/update:

```json
{
  "book_slug": "your_book_name",     ← MUST match directory name
  "book_title": "The Full Book Title",
  "book_author": "Author Name",
  "book_year": "2024",
  ...
}
```

**Common Mistake:** Pre-processing scripts may generate a long slug with the full title. **Always change this to match the directory name.**

### Example Fix:

**Before (WRONG):**
```json
{
  "book_slug": "the-terror-that-comes-in-the-night-an-experience-centered-study-of-supernatural-assault-traditions",
  ...
}
```

**After (CORRECT):**
```json
{
  "book_slug": "the_terror_that_comes_at_night",
  ...
}
```

---

## Step 3: Verify story_positions.json Format

Ensure `story_positions.json` has the correct structure:

```json
{
    "Story Title Here": {
        "start_char": 12345,
        "end_char": 23456,
        "pages": "10-12",
        "keywords": [
            "keyword1",
            "keyword2",
            "keyword3"
        ]
    },
    ...
}
```

**Important:** 
- `keywords` must be an **array of strings**, not a comma-separated string
- Each story must have `start_char`, `end_char`, `pages`, and `keywords`

---

## Step 4: Add Files to Git

Because `story_positions.json` and `stories_meta.json` are normally in `.gitignore` (they're mutable in production), you must **force-add** them for new books:

```bash
# From repository root
git add books/your_book_name/Full_Text.md
git add books/your_book_name/Stories.md
git add -f books/your_book_name/story_positions.json    # Note the -f flag
git add -f books/your_book_name/stories_meta.json       # Note the -f flag

git commit -m "feat: add new book 'Your Book Title'"
git push origin main
```

**Why force-add?** These files are ignored by default to prevent overwriting production edits, but new books need them committed initially.

---

## Step 5: Update Local Environment

After adding the files, rebuild your local search index:

```bash
cd backend

# Set environment variables
$env:USE_DIRECT_SEARCH='true'
$env:DISABLE_AUTH='true'

# Rebuild the search index
python -c "from search.engine_compat import rebuild_search_index; count = rebuild_search_index(); print(f'Rebuilt: {count} documents')"
```

You should see output like:
```
stories_dict is empty, loading from file...
Batches: 100%|████████████████████████████| 35/35 [03:20<00:00,  5.71s/it]
Rebuilt: 1119 documents
```

The count should increase by the number of stories in your new book.

---

## Step 6: Test Locally

Start the backend and frontend to verify the book works:

```bash
# Backend (in backend/)
$env:USE_DIRECT_SEARCH='true'
$env:DISABLE_AUTH='true'
python -m uvicorn main:app --reload --port 8000

# Frontend (in frontend/)
npm run dev
```

Test these features:
1. **Book Archive** - Your book should appear in the list
2. **Story Archive** - Stories should appear as "Unassigned"
3. **Search & Curate** - Stories should be searchable
4. **Source Filter** - Your book should appear in the dropdown and filter correctly

---

## Step 7: Deploy to Production (Render)

After pushing to `main`, Render will automatically deploy. Once the deployment shows **"Live"**, you need to manually sync the new book data:

### 7a. Wait for Deployment
1. Go to https://dashboard.render.com
2. Find your backend service
3. Wait for the deploy triggered by your commit to show **"Live"**

### 7b. Run Sync Commands

Open the **Shell** in Render dashboard and run these commands in order:

```bash
# 1. Reload stories from disk (reads story_positions.json)
python -c "from utils import sync_disk_to_db; sync_disk_to_db()"

# 2. Rebuild search index with new stories
python -c "from search.engine_compat import rebuild_search_index; count = rebuild_search_index(); print(f'Rebuilt: {count} documents')"
```

**Expected Output:**
- First command: Should log "Loaded X stories" (X = old count + new book stories)
- Second command: Should show progress bars and print "Rebuilt: X documents"

This process takes **5-10 minutes** to embed all stories.

---

## Step 8: Verify Production

After the rebuild completes, test on your production site:

1. **Book Archive** - New book appears
2. **Story Archive** - New stories appear as unassigned
3. **Search & Curate** - Can search stories from new book
4. **Source Filter** - Selecting the book shows only its stories

---

## Common Issues & Solutions

### Issue: Stories appear in Book Archive but not Search/Story Archive

**Cause:** `stories_dict.json` wasn't updated with new stories

**Solution:** Run `sync_disk_to_db()` then `rebuild_search_index()` on production

---

### Issue: Source filter shows book name but returns 0 results

**Cause:** `book_slug` in `stories_meta.json` doesn't match directory name

**Solution:** 
1. Update `stories_meta.json` to match directory name
2. Commit and push
3. Re-run `sync_disk_to_db()` on production
4. Re-run `rebuild_search_index()` on production

---

### Issue: Git refuses to add story_positions.json or stories_meta.json

**Cause:** Files are in `.gitignore`

**Solution:** Use `git add -f` to force-add them (see Step 4)

---

### Issue: Rebuild says "1079 documents" instead of the new count

**Cause:** `stories_dict.json` on production is stale

**Solution:** Run `sync_disk_to_db()` BEFORE `rebuild_search_index()`

---

### Issue: `git push` rejected due to file size limit

**Cause:** `documents.json` exceeds GitHub's 100 MB file size limit. `document_store.json` may also trigger a warning at ~80 MB.

**Solution:** Do NOT commit the Haystack files (`documents.json`, `document_store.json`) to git. These are only needed locally to generate the direct search indexes. Instead:
1. Keep `documents.json` and `document_store.json` local only
2. Run the Haystack-to-Direct migration locally (see Step 5)
3. Commit only the direct search files (`stories.faiss`, `stories.faiss.map.json`, `stories_fts.db`) — these are small (~2-10 MB)

---

## Re-Processing an Existing Book

When a book has been re-processed (text cleanup, story boundary changes, title changes):

### What Changes

- `Full_Text.md` — Updated source text
- `Stories.md` — Updated extracted stories (if regenerated)
- `story_positions.json` — New story boundaries, often **new story titles**
- `document_store.json` / `documents.json` — Updated Haystack data with new embeddings

### Critical Considerations

1. **Story titles are identifiers** — If titles change, old titles become orphans in the codex tree and search index. The `sync_disk_to_db()` function on startup will delete DB stories that no longer exist on disk, but codex tree references (`_stories` arrays) may retain orphaned titles.

2. **Do NOT modify `codex_tree.json` as part of re-processing** — A previous attempt to include tree changes in a re-processing commit accidentally deleted 117 stories from OTHER books. The tree file is large and easy to corrupt. Let the site's auto-commit handle tree changes.

3. **Do NOT convert file encodings** — Story positions and metadata files must stay UTF-8. A previous attempt to "fix" UTF-16 encoding corrupted binary data in these files.

4. **Haystack files are too large for GitHub** — `documents.json` typically exceeds 100 MB. Generate direct search indexes locally and commit only those.

### Step-by-Step Re-Processing Workflow

```bash
# 1. Place updated files in books/{slug}/
#    - Full_Text.md, Stories.md, story_positions.json, stories_meta.json

# 2. Verify stories_meta.json book_slug matches directory name
#    (pre-processing may regenerate this with the wrong slug)

# 3. Regenerate direct search indexes from updated Haystack files
cd backend
python -m search.migrate_haystack_to_direct --input ../data/document_store.json --output ../data/

# 4. Stage files (force-add gitignored files)
cd ..
git add books/{slug}/Full_Text.md
git add books/{slug}/Stories.md
git add -f books/{slug}/story_positions.json
git add -f books/{slug}/stories_meta.json
git add data/stories.faiss
git add data/stories.faiss.map.json
git add data/stories_fts.db
# Do NOT add documents.json or document_store.json (too large for GitHub)

# 5. Commit and push
git commit -m "Re-process {Book Title} - text cleanup and updated search indexes"
git push origin main

# 6. After Render deploys, run in Render Shell:
python -c "from utils import sync_disk_to_db; sync_disk_to_db()"
python -c "from search.engine_compat import rebuild_search_index; count = rebuild_search_index(); print(f'Rebuilt: {count} documents')"
```

### If Something Goes Wrong

If a re-processing commit corrupts data:
```bash
# Find the last clean commit
git log --oneline -10

# Hard reset to the clean commit
git reset --hard <commit_hash>

# Force push to overwrite the bad commits
git push --force-with-lease origin main
```

Then start the re-processing workflow fresh. **Do not try to surgically fix corrupted data** — a clean revert is safer even if it means re-doing the processing.

---

## Summary Checklist

Before pushing a new book, verify:

- [ ] Directory name is lowercase with underscores
- [ ] `book_slug` in stories_meta.json matches directory name exactly (**check this twice — it breaks every time**)
- [ ] story_positions.json has correct format (keywords as array)
- [ ] story_positions.json and stories_meta.json are UTF-8 encoded (not UTF-16)
- [ ] All 4 required files exist: Full_Text.md, Stories.md, story_positions.json, stories_meta.json
- [ ] Files added with `git add -f` for the JSON files
- [ ] Direct search indexes rebuilt from Haystack files (if Haystack data was updated)
- [ ] `documents.json` and `document_store.json` are NOT staged (too large for GitHub)
- [ ] Local testing shows book in all 3 views (Book Archive, Story Archive, Search)

After deployment:

- [ ] Render deployment shows "Live"
- [ ] Ran `sync_disk_to_db()` in Render shell
- [ ] Ran `rebuild_search_index()` in Render shell
- [ ] Production shows new book in all views
- [ ] Source filter works correctly for new book

---

## For AI Models Reading This

When a user asks to add or re-process a book, follow this exact sequence:

1. **Verify directory structure** matches the naming convention
2. **Check and fix** `book_slug` in stories_meta.json to match directory name — this has been wrong for every book so far
3. **Verify encoding** — story_positions.json and stories_meta.json must be UTF-8 (check for BOM: first bytes should be `7b`, not `ff fe`)
4. **Regenerate direct search indexes** from Haystack files: `python -m search.migrate_haystack_to_direct --input ../data/document_store.json --output ../data/`
5. **Do NOT stage** `documents.json` or `document_store.json` — they exceed GitHub's 100 MB limit
6. **Do NOT modify** `codex_tree.json` as part of book ingestion — only the site should modify the tree
7. **Do NOT convert** file encodings — leave files as-is if they parse correctly
8. **Commit with force-add** for the JSON files
9. **After deployment**, provide the user with the exact shell commands:
   ```bash
   python -c "from utils import sync_disk_to_db; sync_disk_to_db()"
   python -c "from search.engine_compat import rebuild_search_index; count = rebuild_search_index(); print(f'Rebuilt: {count} documents')"
   ```

Do not skip the `sync_disk_to_db()` step - it must run before rebuilding the search index.
