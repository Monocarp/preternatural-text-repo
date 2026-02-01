# ==================================================================================
# BLOCK 6 RETROFIT: RE-EMBED EXISTING CURATED BOOKS
# ==================================================================================
# Use this version for books that already have:
# - Manually edited boundaries
# - Category assignments
# - Retrofitted metadata (from block_retrofit_optimized.py)
#
# This ONLY creates new embeddings with enriched headers.
# Does NOT change boundaries, assignments, or metadata.

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


def batch_reembed_curated_books():
    """
    Re-embed existing curated books with enriched headers.
    Preserves all boundaries and metadata - ONLY creates new embeddings.
    """
    force = ['christian_mysticism_vol_iv', 'ecology_of_souls_volume_i']  # Books to re-embed
    
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
        batch_size=32
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

        if slug not in force:
            print(f"Skipping {slug} (not in force list)")
            continue

        if slug in indexed_books:
            old_count = len(all_docs)
            all_docs = [doc for doc in all_docs if doc.meta.get("book") != slug]
            print(f"Force-reprocessing {slug}: removed {old_count - len(all_docs)} old docs")

        full_md = os.path.join(path, "Full_Text.md")
        positions_path = os.path.join(path, "story_positions.json")

        if not os.path.exists(full_md):
            print(f"Missing Full_Text.md in {slug}, skipping...")
            continue
            
        if not os.path.exists(positions_path):
            print(f"Missing story_positions.json in {slug}, skipping...")
            continue

        print(f"\n{'='*60}")
        print(f"RE-EMBEDDING: {slug}")
        print(f"{'='*60}")

        # Load existing positions (with metadata from retrofit)
        with open(positions_path, "r", encoding="utf-8") as f:
            positions = json.load(f)
        
        print(f"✓ Loaded {len(positions)} stories from existing story_positions.json")
        
        # Load full text
        with open(full_md, 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        print(f"✓ Loaded full text: {len(full_text):,} characters")

        # Story-level docs with enriched embeddings
        story_docs = []
        skipped = 0
        
        for title, pos in positions.items():
            start = pos.get("start_char", -1)
            end = pos.get("end_char", -1)
            
            if start == -1 or end == -1:
                skipped += 1
                continue
                
            text = full_text[start:end].strip()
            if not text:
                skipped += 1
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
        if skipped > 0:
            print(f"⚠️  Skipped {skipped} stories with invalid boundaries")

        # Embed stories
        print(f"→ Embedding {len(story_docs)} documents...")
        result = embedder.run(story_docs)
        new_embedded = result["documents"]
        new_embedded = ensure_numpy_embedding(new_embedded)

        all_docs.extend(new_embedded)
        newly_added_docs.extend(new_embedded)
        new_docs_count += len(new_embedded)
        print(f"✓ Added {len(new_embedded)} new embedded documents")

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

    # FAISS Index - Rebuild from scratch to avoid duplicates
    print("Building FAISS index from scratch...")
    dimension = 1024
    faiss_index = faiss.IndexFlatL2(dimension)

    all_embeddings = []
    for doc in all_docs:
        if hasattr(doc, 'embedding') and doc.embedding is not None:
            emb = doc.embedding
            if isinstance(emb, list):
                emb = np.array(emb, dtype=np.float32)
            elif hasattr(emb, 'cpu'):
                emb = emb.cpu().numpy().astype(np.float32)
            else:
                emb = np.asarray(emb).astype(np.float32)
            all_embeddings.append(emb)

    if all_embeddings:
        all_embeddings = np.vstack(all_embeddings)
        faiss_index.add(all_embeddings)
        print(f"Added {len(all_embeddings)} vectors to FAISS index")

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
batch_reembed_curated_books()
