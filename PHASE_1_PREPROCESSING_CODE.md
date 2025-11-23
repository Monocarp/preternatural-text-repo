# Pre-Processing Code Changes for Phase 1

## 📝 Copy-Paste Ready Code for Your Step 3 Colab Notebook

Replace your `batch_preprocess()` function with this updated version:

```python
def batch_preprocess():
    """
    PHASE 1 UPDATE: Creates both chunk-level AND story-level embeddings
    - Chunks: For non-story content (commentary, theology, etc.)
    - Stories: For complete story documents (eliminates fragmentation)
    """
    force = []  # Add book slugs here to force reprocessing
    embedder = SentenceTransformersDocumentEmbedder(
        model="BAAI/bge-large-en-v1.5", 
        normalize_embeddings=True
    )
    embedder.warm_up()
    all_docs = []

    for d in os.listdir(books_dir):
        path = os.path.join(books_dir, d)
        if not os.path.isdir(path):
            continue
        slug = d.lower().replace(" ", "_")

        # Skip if already processed (unless forced)
        if slug not in force and os.path.exists(os.path.join(path, "story_positions.json")):
            print(f"Skipping {slug} (already processed)")
            continue

        full_md = os.path.join(path, "Full_Text.md")
        stories_md = os.path.join(path, "Stories.md")
        index_md = os.path.join(path, "grouped_index.md")

        if not all(os.path.exists(p) for p in [full_md, stories_md]):
            print(f"Missing files in {slug}, skipping...")
            continue

        print(f"\n=== Processing {slug} ===")
        
        # Load full text
        with open(full_md, encoding="utf-8") as f:
            full_text = f.read()
        
        # Locate story positions
        positions = locate_story_positions(full_md, stories_md, index_md, slug, path)
        
        # ========== 1. CREATE CHUNK-LEVEL DOCS (EXISTING) ==========
        chunks = chunk_full_md(full_md, positions, slug)
        print(f"→ Created {len(chunks)} chunk documents")
        
        # ========== 2. CREATE STORY-LEVEL DOCS (NEW FOR PHASE 1) ==========
        story_docs = []
        for title, pos_data in positions.items():
            # Skip stories without valid positions
            if pos_data.get("start_char", -1) == -1:
                print(f"  ⚠️  Skipping '{title}' (no valid position)")
                continue
            
            # Extract full story text using character positions
            start = pos_data["start_char"]
            end = pos_data["end_char"]
            story_text = full_text[start:end]
            
            if not story_text.strip():
                print(f"  ⚠️  Skipping '{title}' (empty content)")
                continue
            
            # Create story-level document
            doc = Document(
                content=story_text,  # Full story text for embedding
                meta={
                    "type": "story",  # CRITICAL: Mark as story-level
                    "title": title,
                    "book": slug,
                    "source": slug.replace('_', ' '),
                    "pages": pos_data.get("pages", "Unknown"),
                    "keywords": ", ".join(pos_data.get("keywords", [])),
                    "start_char": start,
                    "end_char": end
                }
            )
            story_docs.append(doc)
        
        print(f"→ Created {len(story_docs)} story documents")
        
        # ========== 3. EMBED BOTH CHUNKS AND STORIES ==========
        all_book_docs = chunks + story_docs
        result = embedder.run(all_book_docs)
        embedded_docs = result["documents"]
        all_docs.extend(embedded_docs)
        
        print(f"→ Embedded {len(embedded_docs)} total documents ({len(chunks)} chunks + {len(story_docs)} stories)")
        
        # Debug: Check if embeddings are actually present
        has_embeddings = sum(1 for d in embedded_docs if hasattr(d, 'embedding') and d.embedding is not None)
        print(f"→ {has_embeddings}/{len(embedded_docs)} documents have valid embeddings")
        
        # Verify story documents have correct metadata
        story_count = sum(1 for d in embedded_docs if d.meta.get("type") == "story")
        chunk_count = sum(1 for d in embedded_docs if d.meta.get("type") != "story")
        print(f"→ Verified: {story_count} story docs, {chunk_count} chunk docs")

    # ========================== SAVE EVERYTHING ==========================
    if all_docs:
        # Build document store
        store = InMemoryDocumentStore()
        store.write_documents(all_docs)
        store_path = os.path.join(data_dir, "document_store.json")
        store.save_to_disk(store_path)
        files.download(store_path)
        
        # Print summary
        total_stories = sum(1 for d in all_docs if d.meta.get("type") == "story")
        total_chunks = sum(1 for d in all_docs if d.meta.get("type") != "story")
        print(f"\n{'='*60}")
        print(f"PHASE 1 PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Total documents: {len(all_docs)}")
        print(f"  - Story-level docs: {total_stories}")
        print(f"  - Chunk-level docs: {total_chunks}")
        print(f"  - Ratio: {total_stories}/{total_chunks} = {total_stories/total_chunks:.2f}")
        print(f"\nExpected ratio: ~0.35-0.40 (more chunks than stories)")
        print(f"{'='*60}\n")
        
        print("✅ document_store.json saved and downloaded")
        print("✅ Next step: Replace backend/data/document_store.json with this file")

# ========================== RUN ==========================
batch_preprocess()
```

---

## 🔍 What's Different?

### **Section 1: Chunk Creation (UNCHANGED)**
```python
chunks = chunk_full_md(full_md, positions, slug)
```
This stays exactly the same - we still need chunks for non-story content.

### **Section 2: Story Creation (NEW)**
```python
story_docs = []
for title, pos_data in positions.items():
    # Skip invalid positions
    if pos_data.get("start_char", -1) == -1:
        continue
    
    # Extract full story
    story_text = full_text[pos_data["start_char"]:pos_data["end_char"]]
    
    # Create document with correct metadata
    doc = Document(
        content=story_text,
        meta={
            "type": "story",      # ← Backend filters on this
            "title": title,       # ← Backend extracts this
            "book": slug,         # ← Backend filters on this
            "pages": ...,
            "keywords": ...,
            "start_char": ...,    # ← Frontend uses this for display
            "end_char": ...       # ← Frontend uses this for display
        }
    )
```

### **Section 3: Embed Together**
```python
all_book_docs = chunks + story_docs
result = embedder.run(all_book_docs)
```
One embedding pass for both types (efficient).

---

## ✅ Validation Checks

After running, verify these outputs:

```
=== Processing christian_mysticism_vol_iv ===
→ Created 523 chunk documents
→ Created 84 story documents
→ Embedded 607 total documents (523 chunks + 84 stories)
→ 607/607 documents have valid embeddings
→ Verified: 84 story docs, 523 chunk docs
```

**Red flags**:
- ❌ "0 story documents" - Check your `positions.items()` loop
- ❌ "0/607 documents have valid embeddings" - Embedder failed
- ❌ Ratio < 0.2 or > 0.5 - Something's wrong with document creation

**Good signs**:
- ✅ Story count matches number of stories in `story_positions.json`
- ✅ All documents have embeddings
- ✅ Ratio is ~0.35-0.40 (typical: 35% stories, 65% chunks)

---

## 🐛 Common Issues

### Issue 1: `KeyError: 'start_char'`

**Cause**: Some positions don't have start_char

**Fix**: Already handled with:
```python
if pos_data.get("start_char", -1) == -1:
    continue
```

### Issue 2: Stories have empty content

**Cause**: Bad character positions in `story_positions.json`

**Debug**:
```python
# Add after extracting story_text:
if len(story_text) < 100:
    print(f"  ⚠️  Short story: '{title}' = {len(story_text)} chars")
```

### Issue 3: Memory error during embedding

**Cause**: Too many documents at once

**Fix**: Process in batches:
```python
# Replace single embedding with batches
BATCH_SIZE = 100
for i in range(0, len(all_book_docs), BATCH_SIZE):
    batch = all_book_docs[i:i+BATCH_SIZE]
    result = embedder.run(batch)
    all_docs.extend(result["documents"])
```

---

## 📊 Expected Output Size

| Component | Before (Chunks Only) | After (Chunks + Stories) |
|-----------|---------------------|-------------------------|
| Documents | ~6,000 | ~8,500 (+40%) |
| File size | ~450 MB | ~650 MB (+45%) |
| Stories | Embedded in chunks | Embedded as separate docs |

**Note**: File size increases because each story is embedded twice:
1. As part of chunks (for context)
2. As a complete story (for direct search)

This is intentional and worth the storage cost.

---

## 🚀 Deployment Steps

1. **Run updated notebook in Colab** (30-60 minutes)
2. **Download `document_store.json`**
3. **Backup old file**:
   ```bash
   mv backend/data/document_store.json backend/data/document_store_old.json
   ```
4. **Copy new file**:
   ```bash
   cp ~/Downloads/document_store.json backend/data/
   ```
5. **Test locally**:
   ```bash
   cd backend
   python main.py
   # In another terminal:
   curl -X POST http://localhost:8000/api/search -H "Content-Type: application/json" -d '{"query": "possession", "top_k": 10}'
   ```
6. **Deploy to production**

---

## 🎯 Success Criteria

After deployment, you should see:

1. **In backend logs**:
   ```
   Loaded 8453 documents
   Document types: {'story': 2219, 'non_story': 6234}
   ```

2. **In search results**:
   - Multi-chunk stories appear as ONE result
   - Rank positions improve for those stories
   - Overall result count similar to before

3. **In user behavior**:
   - Higher click-through on top result
   - Fewer "back to search" actions
   - More "find similar" usage

**You're ready to process!** Let me know if you hit any snags.
