# backend/search/migrate_haystack_to_direct.py
"""
Migration script: Convert Haystack InMemoryDocumentStore to Direct FAISS + SQLite.

This script:
1. Loads the existing document_store.json (Haystack format)
2. Extracts all documents with embeddings
3. Creates new FAISS index with ID mapping
4. Creates SQLite FTS5 index for keyword search
5. Validates the migration

Run from backend directory:
    python -m search.migrate_haystack_to_direct

Or with explicit paths:
    python -m search.migrate_haystack_to_direct --input data/document_store.json --output data/
"""

import json
import logging
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from search.models import StoryDocument
from search.faiss_index import FAISSIndexManager
from search.fts_index import FTS5Index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_haystack_document_store(json_path: str) -> List[Dict[str, Any]]:
    """
    Load documents from Haystack's InMemoryDocumentStore JSON export.
    
    The JSON format is:
    {
        "documents": [
            {
                "id": "...",
                "content": "...",
                "meta": {...},
                "embedding": [...]
            },
            ...
        ]
    }
    """
    logger.info(f"Loading Haystack document store from {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = data.get("documents", [])
    logger.info(f"Found {len(documents)} documents")
    
    return documents


def convert_to_story_documents(haystack_docs: List[Dict]) -> List[StoryDocument]:
    """Convert Haystack document dicts to StoryDocument objects."""
    story_docs = []
    skipped = 0
    
    for doc in haystack_docs:
        # Skip non-story documents
        doc_type = doc.get("meta", {}).get("type", "unknown")
        if doc_type != "story":
            skipped += 1
            continue
        
        # Extract embedding
        embedding = doc.get("embedding")
        if embedding:
            embedding = np.array(embedding, dtype=np.float32)
        else:
            logger.warning(f"Document {doc.get('id')} has no embedding, will need re-embedding")
        
        story_doc = StoryDocument(
            id=doc["id"],
            content=doc.get("content", ""),
            meta=doc.get("meta", {}),
            embedding=embedding,
            score=0.0
        )
        story_docs.append(story_doc)
    
    logger.info(f"Converted {len(story_docs)} story documents (skipped {skipped} non-story)")
    return story_docs


def create_faiss_index(docs: List[StoryDocument], output_path: str) -> FAISSIndexManager:
    """Create and populate FAISS index from story documents."""
    logger.info("Creating FAISS index...")
    
    # Filter docs with valid embeddings
    docs_with_embeddings = [d for d in docs if d.embedding is not None]
    if len(docs_with_embeddings) < len(docs):
        logger.warning(f"{len(docs) - len(docs_with_embeddings)} documents missing embeddings")
    
    faiss_manager = FAISSIndexManager(dimension=1024)
    faiss_manager.create_index()
    
    # Prepare data
    doc_ids = [d.id for d in docs_with_embeddings]
    embeddings = np.vstack([d.embedding for d in docs_with_embeddings])
    metadata = [d.meta for d in docs_with_embeddings]
    
    # Add to index
    faiss_manager.add_documents(doc_ids, embeddings, metadata)
    
    # Save
    faiss_manager.save(output_path)
    logger.info(f"Saved FAISS index with {faiss_manager.count} vectors to {output_path}")
    
    return faiss_manager


def create_fts_index(docs: List[StoryDocument], output_path: str) -> FTS5Index:
    """Create and populate FTS5 index from story documents."""
    logger.info("Creating FTS5 index...")
    
    fts_index = FTS5Index(output_path)
    fts_index.clear()  # Start fresh
    
    # Prepare batch data
    batch_docs = []
    for doc in docs:
        batch_docs.append({
            'doc_id': doc.id,
            'title': doc.meta.get("title", ""),
            'content': doc.content,
            'book_slug': doc.meta.get("book", ""),
            'pages': doc.meta.get("pages", ""),
            'keywords': doc.meta.get("keywords", ""),
            'start_char': doc.meta.get("start_char", 0),
            'end_char': doc.meta.get("end_char", 0),
            'extra_metadata': doc.meta  # Store full metadata including people, locations, etc.
        })
    
    fts_index.add_documents_batch(batch_docs)
    
    logger.info(f"Created FTS5 index with {fts_index.get_document_count()} documents at {output_path}")
    return fts_index


def validate_migration(
    original_count: int,
    faiss_manager: FAISSIndexManager,
    fts_index: FTS5Index
) -> bool:
    """Validate that migration was successful."""
    logger.info("Validating migration...")
    
    faiss_count = faiss_manager.count
    fts_count = fts_index.get_document_count()
    
    logger.info(f"Original documents: {original_count}")
    logger.info(f"FAISS vectors: {faiss_count}")
    logger.info(f"FTS5 documents: {fts_count}")
    
    # Check counts match
    if faiss_count != fts_count:
        logger.error(f"Count mismatch: FAISS={faiss_count}, FTS5={fts_count}")
        return False
    
    # Test searches
    test_queries = ["demon", "vision", "prayer", "apparition"]
    
    for query in test_queries:
        # Test FTS5
        fts_results = fts_index.search(query, top_k=5)
        if fts_results:
            logger.info(f"FTS5 search '{query}': {len(fts_results)} results, top: {fts_results[0][2].get('title', 'unknown')}")
        else:
            logger.warning(f"FTS5 search '{query}': no results")
    
    logger.info("Migration validation complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="Migrate Haystack DocumentStore to Direct FAISS + SQLite")
    parser.add_argument(
        "--input", "-i",
        default="data/document_store.json",
        help="Path to Haystack document_store.json"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/",
        help="Output directory for new indices"
    )
    parser.add_argument(
        "--faiss-name",
        default="stories.faiss",
        help="Filename for FAISS index"
    )
    parser.add_argument(
        "--fts-name",
        default="stories_fts.db",
        help="Filename for FTS5 database"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    backend_dir = Path(__file__).parent.parent
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = backend_dir / input_path
    
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = backend_dir / output_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    faiss_path = output_dir / args.faiss_name
    fts_path = output_dir / args.fts_name
    
    logger.info(f"Input: {input_path}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"FAISS index: {faiss_path}")
    logger.info(f"FTS5 database: {fts_path}")
    
    # Check input exists
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    # Load Haystack data
    haystack_docs = load_haystack_document_store(str(input_path))
    
    # Convert to StoryDocuments
    story_docs = convert_to_story_documents(haystack_docs)
    
    if not story_docs:
        logger.error("No story documents found!")
        sys.exit(1)
    
    # Create new indices
    faiss_manager = create_faiss_index(story_docs, str(faiss_path))
    fts_index = create_fts_index(story_docs, str(fts_path))
    
    # Validate
    success = validate_migration(len(story_docs), faiss_manager, fts_index)
    
    if success:
        logger.info("=" * 60)
        logger.info("MIGRATION SUCCESSFUL!")
        logger.info("=" * 60)
        logger.info(f"FAISS index: {faiss_path} ({faiss_manager.count} vectors)")
        logger.info(f"FAISS mapping: {faiss_path}.map.json")
        logger.info(f"FTS5 database: {fts_path} ({fts_index.get_document_count()} documents)")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Backup the old document_store.json")
        logger.info("2. Update search/__init__.py to use the new engine")
        logger.info("3. Test the application")
    else:
        logger.error("Migration validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
