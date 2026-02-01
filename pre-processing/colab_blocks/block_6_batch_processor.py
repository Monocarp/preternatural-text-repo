# ==================================================================================
# BLOCK 6: MAIN BATCH PROCESSOR
# ==================================================================================
# This is the main entry point that orchestrates the entire pipeline

def serialize_value(val):
    """Helper to serialize values safely (handles numpy types)."""
    if isinstance(val, np.ndarray):
        return val.tolist()
    elif isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    elif isinstance(val, dict):
        return {serialize_value(k): serialize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [serialize_value(x) for x in val]
    else:
        return val


def serialize_doc(doc):
    """Helper to serialize entire doc."""
    item = {
        "id": str(doc.id) if doc.id is not None else None,
        "content": doc.content,
        "meta": serialize_value(doc.meta)
    }
    if hasattr(doc, 'embedding') and doc.embedding is not None:
        emb = doc.embedding
        item["embedding"] = serialize_value(emb)
    return item


def ensure_numpy_embedding(docs):
    """Helper to convert embedding to NumPy float32."""
    for doc in docs:
        if hasattr(doc, 'embedding') and doc.embedding is not None:
            if hasattr(doc.embedding, 'cpu'):
                doc.embedding = doc.embedding.cpu().numpy().astype(np.float32)
            elif not isinstance(doc.embedding, np.ndarray):
                doc.embedding = np.array(doc.embedding, dtype=np.float32)
    return docs


def batch_preprocess():
    """Main batch processor with enhanced metadata extraction."""
    force = []  # Add book slugs here to force reprocess
    
    # Check if GPU is available
    import torch
    from haystack.utils import ComponentDevice
    
    if torch.cuda.is_available():
        device = ComponentDevice.from_str("cuda:0")
        print(f"🔧 Using GPU for embeddings")
    else:
        device = ComponentDevice.from_str("cpu")
        print(f"🔧 Using CPU for embeddings")
    
    embedder = SentenceTransformersDocumentEmbedder(
        model="BAAI/bge-large-en-v1.5",
        normalize_embeddings=True,
        device=device,
        batch_size=32   # Larger batch size for faster processing
    )
    embedder.warm_up()

    # Paths
    docs_path = os.path.join(data_dir, "documents.json")
    faiss_path = os.path.join(data_dir, "faiss_index.bin")
    store_path = os.path.join(data_dir, "document_store.json")

    # Load existing documents
    existing_docs = []
    if os.path.exists(docs_path):
        print("Loading existing documents.json...")
        with open(docs_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        for item in raw:
            doc = Document(
                content=item["content"],
                meta=item.get("meta", {}),
                id=item.get("id")
            )
            if "embedding" in item and item["embedding"] is not None:
                doc.embedding = np.array(item["embedding"], dtype=np.float32)
            existing_docs.append(doc)
        print(f"Loaded {len(existing_docs)} existing documents")

    all_docs = existing_docs.copy()
    indexed_books = {doc.meta.get("book") for doc in existing_docs if doc.meta.get("book")}
    newly_added_docs = []
    new_docs_count = 0

    # Process books
    for d in os.listdir(books_dir):
        path = os.path.join(books_dir, d)
        if not os.path.isdir(path):
            continue
        slug = d.lower().replace(" ", "_")

        if slug in indexed_books and slug not in force:
            print(f"Skipping {slug} (already indexed)")
            continue

        if slug in force and slug in indexed_books:
            old_count = len(all_docs)
            all_docs = [doc for doc in all_docs if doc.meta.get("book") != slug]
            print(f"Force-reprocessing {slug}: removed {old_count - len(all_docs)} old docs")

        full_md = os.path.join(path, "Full_Text.md")
        stories_md = os.path.join(path, "Stories.md")
        index_md = os.path.join(path, "grouped_index.md")

        if not all(os.path.exists(p) for p in [full_md, stories_md]):
            print(f"Missing files in {slug}, skipping...")
            continue

        print(f"\n{'='*60}")
        print(f"PROCESSING: {slug}")
        print(f"{'='*60}")

        # Step 1: Locate story positions
        positions, full_text = locate_story_positions(full_md, stories_md, index_md, slug, path)
        
        # TESTING: Limit to first 5 stories
        print(f"⚠️  TESTING MODE: Processing only first 5 stories")
        story_titles = list(positions.keys())
        if len(story_titles) > 5:
            positions = {title: positions[title] for title in story_titles[:5]}
        
        # Step 2: Extract structured metadata (NEW)
        positions, review_queue = extract_structured_metadata(positions, full_text, slug, path)
        
        # Step 3: Save enhanced story_positions.json
        positions_path = os.path.join(path, "story_positions.json")
        with open(positions_path, "w", encoding="utf-8") as f:
            json.dump(positions, f, indent=2, ensure_ascii=False)
        print(f"story_positions.json saved with enhanced metadata")
        files.download(positions_path)
        
        # Step 4: Save review queue if any
        save_review_queue(review_queue, path, slug)
        
        # Step 5: Chunk with enhanced metadata
        chunks = chunk_full_md(full_md, positions, slug)
        print(f"→ {len(chunks)} chunks")

        # Step 6: Story-level docs with enhanced metadata
        story_docs = []
        for title, pos in positions.items():
            if pos.get("start_char", -1) == -1:
                continue
            text = full_text[pos["start_char"]:pos["end_char"]].strip()
            if not text:
                continue
            
            # Build semantic enrichment header
            enrichment_parts = [f"Title: {title}"]
            
            # Add keywords if present
            keywords = pos.get("keywords", [])
            if keywords:
                enrichment_parts.append(f"Keywords: {', '.join(keywords[:15])}")
            
            # Add locations if present
            locations = pos.get("locations", {})
            loc_parts = []
            if locations.get("cities"):
                loc_parts.extend(locations["cities"][:3])
            if locations.get("regions"):
                loc_parts.extend(locations["regions"][:2])
            if locations.get("countries"):
                loc_parts.extend(locations["countries"][:2])
            if loc_parts:
                enrichment_parts.append(f"Locations: {', '.join(loc_parts)}")
            
            # Add temporal if present
            temporal = pos.get("temporal", {})
            if temporal.get("years"):
                years_str = ', '.join(str(y) for y in temporal["years"][:3])
                enrichment_parts.append(f"Years: {years_str}")
            elif temporal.get("centuries"):
                cent_str = ', '.join(f"{c}th century" for c in temporal["centuries"][:2])
                enrichment_parts.append(f"Period: {cent_str}")
            
            # Construct enriched content
            enrichment_header = " | ".join(enrichment_parts)
            enriched_content = f"{enrichment_header}\n\n{text}"
            
            story_docs.append(Document(
                content=enriched_content,
                meta={
                    "type": "story",
                    "title": title,
                    "book": slug,
                    "source": slug.replace('_', ' '),
                    "pages": pos.get("pages", "Unknown"),
                    "keywords": ", ".join(pos.get("keywords", [])),
                    "start_char": pos["start_char"],
                    "end_char": pos["end_char"],
                    # Enhanced metadata
                    "centuries": pos.get("temporal", {}).get("centuries", []),
                    "years": pos.get("temporal", {}).get("years", []),
                    "countries": pos.get("locations", {}).get("countries", []),
                    "cities": pos.get("locations", {}).get("cities", []),
                    "topics": pos.get("topics", {}).get("primary", []),
                    "confidence": pos.get("confidence", 0),
                    "status": pos.get("status", "UNKNOWN")
                }
            ))
        print(f"→ {len(story_docs)} full stories (with enriched embeddings)")

        # Step 7: Embed
        all_new_docs = chunks + story_docs
        result = embedder.run(all_new_docs)
        new_embedded = result["documents"]
        new_embedded = ensure_numpy_embedding(new_embedded)

        all_docs.extend(new_embedded)
        newly_added_docs.extend(new_embedded)
        new_docs_count += len(new_embedded)
        print(f"→ Added {len(new_embedded)} new embedded documents")

    # Save everything
    if not all_docs:
        print("No documents to save.")
        return

    emb_count = sum(1 for d in all_docs if getattr(d, 'embedding', None) is not None)
    print(f"\nPre-save check: {emb_count}/{len(all_docs)} docs have embeddings")

    # documents.json
    docs_data = [serialize_doc(d) for d in all_docs]
    with open(docs_path, "w", encoding="utf-8") as f:
        json.dump(docs_data, f, indent=2, ensure_ascii=False)
    files.download(docs_path)
    print(f"documents.json saved → {len(all_docs)} total docs")

    # FAISS Index
    if os.path.exists(faiss_path):
        print("Loading existing FAISS index...")
        faiss_index = faiss.read_index(faiss_path)
        print(f"Loaded FAISS index with {faiss_index.ntotal} vectors")
    else:
        dimension = 1024
        faiss_index = faiss.IndexFlatL2(dimension)
        print("No existing FAISS; starting fresh index")

    new_embeddings = []
    for doc in newly_added_docs:
        if hasattr(doc, 'embedding') and doc.embedding is not None:
            emb = doc.embedding
            if isinstance(emb, list):
                emb = np.array(emb, dtype=np.float32)
            elif hasattr(emb, 'cpu'):
                emb = emb.cpu().numpy().astype(np.float32)
            else:
                emb = np.asarray(emb).astype(np.float32)
            new_embeddings.append(emb)

    if new_embeddings:
        new_embeddings = np.vstack(new_embeddings)
        faiss_index.add(new_embeddings)
        print(f"Appended {len(new_embeddings)} new vectors to FAISS")

    faiss.write_index(faiss_index, faiss_path)
    files.download(faiss_path)
    print(f"faiss_index.bin updated → {faiss_index.ntotal} total vectors")

    # Document Store
    store_docs = []
    for doc in all_docs:
        emb_list = None
        if hasattr(doc, 'embedding') and doc.embedding is not None:
            emb = doc.embedding
            if isinstance(emb, np.ndarray):
                emb_list = emb.tolist()
            elif isinstance(emb, list):
                emb_list = emb[:]
            else:
                emb_list = np.array(emb).tolist()

        store_doc = Document(
            content=doc.content,
            meta=doc.meta,
            embedding=emb_list,
            id=doc.id
        )
        store_docs.append(store_doc)

    store = InMemoryDocumentStore()
    store.write_documents(store_docs)
    store.save_to_disk(store_path)
    files.download(store_path)
    print("document_store.json saved")

    # Summary
    stories = sum(1 for d in all_docs if d.meta.get("type") == "story")
    chunks = len(all_docs) - stories
    print(f"\n{'='*60}")
    print(f"SUCCESS! Total: {len(all_docs)} docs ({stories} stories + {chunks} chunks)")
    print(f"Growth this run: +{new_docs_count}")
    print(f"{'='*60}")


# ==================================================================================
# UNCOMMENT TO RUN:
# ==================================================================================
# batch_preprocess()
