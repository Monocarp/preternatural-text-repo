# backend/utils.py
import json
import re
import os
import subprocess
from docx import Document as DocxDocument
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import logging
from collections import Counter
import numpy as np
import torch # For torch.float16 in model_kwargs
import base64
import zipfile
import io
from huggingface_hub import HfApi
from haystack import Pipeline, Document
from haystack.components.embedders import SentenceTransformersTextEmbedder, SentenceTransformersDocumentEmbedder
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever, InMemoryBM25Retriever
from haystack.components.joiners import DocumentJoiner
from haystack.document_stores.in_memory import InMemoryDocumentStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Book, Story, CodexNode, NodeStory
from dotenv import load_dotenv
import time
# Load .env.local from project root (since we're in backend subdir)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.local'))
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Cache Management
# ------------------------------------------------------------------ #
_tree_cache = None
_cache_timestamp = 0
_last_data_change = 0

def invalidate_cache():
    """Invalidate both tree and assigned titles caches."""
    global _last_data_change
    _last_data_change = time.monotonic()
    clear_assigned_titles_cache()  # Add this line
    logger.info(f"Cache invalidated at timestamp {_last_data_change:.2f}")

def get_cached_tree():
    """Get tree from cache, reload if invalidated"""
    global _tree_cache, _cache_timestamp, _last_data_change
    
    if _tree_cache is None:
        logger.info("Loading tree for the first time")
        _tree_cache = load_codex_tree()
        _cache_timestamp = time.monotonic()
    elif _last_data_change > _cache_timestamp:
        logger.info(f"Cache expired (last change: {_last_data_change:.2f}, cache from: {_cache_timestamp:.2f}), reloading tree")
        _tree_cache = load_codex_tree()
        _cache_timestamp = time.monotonic()
    else:
        logger.debug(f"Using cached tree (age: {time.monotonic() - _cache_timestamp:.2f}s)")
    
    return _tree_cache
# Paths (relative to root from backend)
books_dir = "../books/"
data_dir = "../data/"
document_store_path = os.path.join(data_dir, "document_store.json")
codex_tree_path = os.path.join(data_dir, "codex_tree.json")
stories_dict_path = os.path.join(data_dir, "stories_dict.json")
# DB Connection
DB_URL = os.getenv("POSTGRES_PRISMA_URL") # Pooled for serverless
USE_DB = False
engine = None
SessionLocal = None
if DB_URL:
    if "postgres" in DB_URL:
        DB_URL = DB_URL.replace("postgres://", "postgresql://")
    try:
        engine = create_engine(DB_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        # Create tables if not exist
        Base.metadata.create_all(bind=engine)
        USE_DB = True
        logger.info("Database connection established")
    except Exception as e:
        logger.warning(f"Failed to connect to database: {e}. Falling back to JSON storage.")
        USE_DB = False
else:
    logger.info("No database URL provided. Using JSON storage.")
# Global flat story storage (in-memory cache; load from DB)
stories_dict = {}

# Cache for book metadata to avoid repeated DB queries
_book_metadata_cache = {}

def get_book_metadata(book_slug):
    """Get book metadata with caching to avoid repeated DB queries"""
    if book_slug in _book_metadata_cache:
        return _book_metadata_cache[book_slug]
    
    book_info = {}
    if USE_DB and SessionLocal:
        try:
            with SessionLocal() as db:
                from models import Book
                book = db.query(Book).filter_by(slug=book_slug).first()
                if book:
                    book_info = {
                        "book_title": book.title,
                        "book_author": book.author,
                        "book_year": book.year
                    }
        except Exception as e:
            logger.debug(f"Could not fetch book metadata for {book_slug}: {e}")
    
    _book_metadata_cache[book_slug] = book_info
    return book_info

def clear_book_metadata_cache():
    """Clear the book metadata cache (call when books are updated)"""
    global _book_metadata_cache
    _book_metadata_cache = {}
    logger.info("Cleared book metadata cache")

def preload_book_metadata():
    """Preload all book metadata at startup to avoid any DB queries during search"""
    global _book_metadata_cache
    
    if not USE_DB or not SessionLocal:
        logger.info("No database - loading book metadata from stories_meta.json files")
        # Fallback: Load from JSON files
        try:
            for book_slug in os.listdir(books_dir):
                book_path = os.path.join(books_dir, book_slug)
                if os.path.isdir(book_path) and not book_slug.startswith('.'):
                    meta_path = os.path.join(book_path, "stories_meta.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                            _book_metadata_cache[book_slug] = {
                                "book_title": meta.get("book_title", book_slug),
                                "book_author": meta.get("book_author", "Unknown"),
                                "book_year": meta.get("book_year", "")
                            }
                        except Exception as e:
                            logger.warning(f"Failed to load metadata from {meta_path}: {e}")
            logger.info(f"Loaded metadata from JSON files for {len(_book_metadata_cache)} books")
        except Exception as e:
            logger.error(f"Failed to load book metadata from JSON: {e}")
        return
    
    # Database available - load from DB
    try:
        with SessionLocal() as db:
            from models import Book
            books = db.query(Book).all()
            for book in books:
                _book_metadata_cache[book.slug] = {
                    "book_title": book.title,
                    "book_author": book.author,
                    "book_year": book.year
                }
        logger.info(f"Preloaded metadata from database for {len(_book_metadata_cache)} books")
    except Exception as e:
        logger.error(f"Failed to preload book metadata from database: {e}")
        # Fallback to JSON if DB fails
        logger.info("Falling back to JSON files for book metadata")
        for book_slug in os.listdir(books_dir):
            book_path = os.path.join(books_dir, book_slug)
            if os.path.isdir(book_path) and not book_slug.startswith('.'):
                meta_path = os.path.join(book_path, "stories_meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        _book_metadata_cache[book_slug] = {
                            "book_title": meta.get("book_title", book_slug),
                            "book_author": meta.get("book_author", "Unknown"),
                            "book_year": meta.get("book_year", "")
                        }
                    except Exception as e:
                        logger.warning(f"Failed to load metadata from {meta_path}: {e}")
        logger.info(f"Loaded metadata from JSON fallback for {len(_book_metadata_cache)} books")
# Lazy-load full MD texts and story positions {book_slug: data}
full_mds = {}
story_positions = {}
def load_full_md(book_slug):
    if book_slug not in full_mds:
        md_path = os.path.join(books_dir, book_slug, "Full_Text.md")
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                full_mds[book_slug] = f.read()
            logger.debug(f"Loaded Full_Text.md for {book_slug}, length: {len(full_mds[book_slug])}")
        except Exception as e:
            logger.error(f"Failed to load Full_Text.md for {book_slug}: {e}")
            full_mds[book_slug] = ""
    return full_mds[book_slug]
def load_story_positions(book_slug):
    if book_slug not in story_positions:
        pos_path = os.path.join(books_dir, book_slug, "story_positions.json")
        try:
            with open(pos_path, "r", encoding="utf-8") as f:
                story_positions[book_slug] = json.load(f)
            logger.debug(f"Loaded story_positions for {book_slug} with {len(story_positions[book_slug])} entries")
        except Exception as e:
            logger.error(f"Failed to load story_positions.json for {book_slug}: {e}")
            story_positions[book_slug] = {}
    return story_positions[book_slug]
def save_story_positions(book_slug):
    """Save story positions to JSON file"""
    pos_path = os.path.join(books_dir, book_slug, "story_positions.json")
    try:
        with open(pos_path, "w", encoding="utf-8") as f:
            json.dump(story_positions[book_slug], f, indent=4, ensure_ascii=False)
        logger.info(f"Saved story_positions for {book_slug}")
        return True
    except Exception as e:
        logger.error(f"Failed to save story_positions.json for {book_slug}: {e}")
        return False
def update_story_boundaries(book_slug, title, start_char, end_char):
    """Update story boundaries in both JSON and database"""
    # Load positions if not already loaded
    positions = load_story_positions(book_slug)
   
    if title not in positions:
        logger.warning(f"Story {title} not found in {book_slug}")
        return False
   
    # Update in-memory cache
    positions[title]["start_char"] = start_char
    positions[title]["end_char"] = end_char
    story_positions[book_slug] = positions
   
    # Update stories_dict cache
    if title in stories_dict:
        stories_dict[title]["start_char"] = start_char
        stories_dict[title]["end_char"] = end_char
   
    # Save to JSON file
    save_success = save_story_positions(book_slug)
   
    # Update database if available
    if USE_DB and SessionLocal:
        try:
            from models import Story
            with SessionLocal() as db:
                story = db.query(Story).filter_by(title=title).first()
                if story:
                    story.start_char = start_char
                    story.end_char = end_char
                    db.commit()
                    logger.info(f"Updated story {title} boundaries in database")
                else:
                    logger.warning(f"Story {title} not found in database")
        except Exception as e:
            logger.error(f"Failed to update database for {title}: {e}")
   
    # Invalidate cache since data changed
    invalidate_cache()
    logger.info(f"Invalidated cache after updating boundaries for {title}")
   
    return save_success
def update_story_title(book_slug, old_title, new_title):
    """Update story title in JSON, database, and all references"""
    global stories_dict, document_store
    
    # Update codex tree first
    try:
        tree = load_codex_tree()
        def replace_title_in_tree(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == '_stories' and isinstance(value, list):
                        for i, t in enumerate(value):
                            if t == old_title:
                                value[i] = new_title
                    elif isinstance(value, (dict, list)):
                        replace_title_in_tree(value)
            elif isinstance(node, list):
                for i, t in enumerate(node):
                    if t == old_title:
                        node[i] = new_title
        replace_title_in_tree(tree)
        save_codex_tree_to_json(tree)
        logger.info(f"Updated codex tree: replaced '{old_title}' with '{new_title}'")
    except Exception as e:
        logger.error(f"Failed to update codex tree: {e}")
        # Don't fail the whole operation

    # Load positions if not already loaded
    positions = load_story_positions(book_slug)
   
    if old_title not in positions:
        logger.warning(f"Story '{old_title}' not found in {book_slug}")
   
    if old_title in positions:
        positions[new_title] = positions.pop(old_title)
        story_positions[book_slug] = positions
   
    # Update stories_dict cache
    if old_title in stories_dict:
        story_data = stories_dict.pop(old_title)
        story_data["title"] = new_title
        stories_dict[new_title] = story_data
   
    # Save to JSON files
    save_success = save_story_positions(book_slug)
    
    # Also save stories_dict.json
    try:
        with open(stories_dict_path, "w") as f:
            json.dump(stories_dict, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save stories_dict.json: {e}")
   
    # Update database if available
    if USE_DB and SessionLocal:
        try:
            from models import Story
            with SessionLocal() as db:
                story = db.query(Story).filter_by(title=old_title, book_slug=book_slug).first()
                if story:
                    story.title = new_title
                    db.commit()
                    logger.info(f"Updated story title in database: '{old_title}' -> '{new_title}'")
                    # Note: NodeStory relationships are preserved via story.id (foreign key)
                else:
                    logger.warning(f"Story '{old_title}' not found in database")
        except Exception as e:
            logger.error(f"Failed to update database title for '{old_title}': {e}")
            return False
   
    # Update document store metadata
    if document_store:
        try:
            # Find all documents that contain this story and update the title
            # Story-level documents have title directly in meta, not nested under "stories"
            updated_docs = []
            for doc in document_store.filter_documents({}):
                # Check if this is a story document with matching title
                if doc.meta.get("title") == old_title:
                    doc.meta["title"] = new_title
                    updated_docs.append(doc)
                    logger.info(f"Found document to update: {doc.id} with title '{old_title}'")
                # Also check for any nested stories arrays (for backward compatibility)
                elif "stories" in doc.meta:
                    story_updated = False
                    for story in doc.meta["stories"]:
                        if story.get("title") == old_title:
                            story["title"] = new_title
                            story_updated = True
                    if story_updated:
                        updated_docs.append(doc)
            
            if updated_docs:
                logger.info(f"Updating {len(updated_docs)} documents in document store")
                # Convert embeddings to lists for updated docs
                for doc in updated_docs:
                    if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                        doc.embedding = doc.embedding.tolist()
                # Re-save the document store with updated metadata
                document_store.delete_documents([doc.id for doc in updated_docs])
                document_store.write_documents(updated_docs)
                
                # Convert ALL document embeddings to lists before saving
                all_docs = list(document_store.filter_documents({}))
                docs_to_convert = []
                for doc in all_docs:
                    if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                        doc.embedding = doc.embedding.tolist()
                        docs_to_convert.append(doc)
                
                if docs_to_convert:
                    document_store.delete_documents([doc.id for doc in docs_to_convert])
                    document_store.write_documents(docs_to_convert)
                
                # Save to disk
                document_store.save_to_disk(document_store_path)
                logger.info(f"Updated document store metadata for {len(updated_docs)} documents and saved to disk")
            else:
                logger.warning(f"No documents found with title '{old_title}' in document store")
        except Exception as e:
            logger.error(f"Failed to update document store metadata: {e}", exc_info=True)
            # Don't fail the whole operation for this

    # Invalidate cache since data changed
    invalidate_cache()
    logger.info(f"Invalidated cache after updating title from '{old_title}' to '{new_title}'")

    return True
# Discover books dynamically
books = [d for d in os.listdir(books_dir) if os.path.isdir(os.path.join(books_dir, d)) and not d.startswith('.')]
sources = ["All Sources"] + sorted(books)
logger.info(f"Discovered books: {sources}")
# Load document store
document_store = None
if os.path.exists(document_store_path):
    logger.info("Loading document store from JSON...")
    try:
        document_store = InMemoryDocumentStore.load_from_disk(document_store_path)
        logger.info(f"Loaded {document_store.count_documents()} documents")
        loaded_docs = document_store.filter_documents({})
        doc_types = Counter(doc.meta.get("type", "unknown") for doc in loaded_docs)
        sample_ids = [doc.id for doc in loaded_docs[:3]]
        sample_metadata = [doc.meta for doc in loaded_docs[:3]]
        sample_content = [doc.content[:50] for doc in loaded_docs[:3]]
        logger.info(f"Document types: {dict(doc_types)}, Sample IDs: {sample_ids}, Sample Metadata: {sample_metadata}, Sample Content: {sample_content}")
        if doc_types.get("story", 0) == 0:
            logger.error("No 'story' type documents found; searches may fail.")
        # Convert embeddings to numpy arrays if needed
        for doc in loaded_docs:
            if doc.embedding is not None and isinstance(doc.embedding, list):
                try:
                    doc.embedding = np.array(doc.embedding, dtype=np.float32)
                except Exception as e:
                    logger.warning(f"Failed to convert embedding for doc {doc.id}: {e}; setting to None")
                    doc.embedding = None
        has_embeddings = any(doc.embedding is not None and len(doc.embedding) == 1024 for doc in loaded_docs)
        logger.info(f"Documents have valid embeddings: {has_embeddings}")
        # Re-embedding disabled - embeddings should be pre-computed
    except Exception as e:
        logger.error(f"Failed to load document store: {e}. Creating new empty document store.")
        document_store = InMemoryDocumentStore()
else:
    logger.error("document_store.json not found.")
    document_store = InMemoryDocumentStore()
# Set up Haystack pipelines
logger.debug("Setting up Haystack pipelines...")
import os
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "bge-large-en-v1.5")
MODEL_PATH = MODEL_DIR if os.path.exists(MODEL_DIR) else "BAAI/bge-large-en-v1.5"
embedder_both = SentenceTransformersTextEmbedder(model=MODEL_PATH, normalize_embeddings=True)
embedder_both.warm_up()
retriever_embedding_both = InMemoryEmbeddingRetriever(document_store=document_store)
retriever_bm25_both = InMemoryBM25Retriever(document_store=document_store)
joiner = DocumentJoiner(
    join_mode="reciprocal_rank_fusion",
    weights=[0.5, 0.5]
)
both_pipeline = Pipeline()
both_pipeline.add_component("embedder", embedder_both)
both_pipeline.add_component("retriever_embedding", retriever_embedding_both)
both_pipeline.add_component("retriever_bm25", retriever_bm25_both)
both_pipeline.add_component("joiner", joiner)
both_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
both_pipeline.connect("retriever_embedding", "joiner")
both_pipeline.connect("retriever_bm25", "joiner")
logger.info(f"Both pipeline components: {list(both_pipeline.graph.nodes.keys())}")
retriever_bm25_key = InMemoryBM25Retriever(document_store=document_store)
keyword_pipeline = Pipeline()
keyword_pipeline.add_component("retriever_bm25", retriever_bm25_key)
logger.info(f"Keyword pipeline components: {list(keyword_pipeline.graph.nodes.keys())}")
embedder_sem = SentenceTransformersTextEmbedder(model=MODEL_PATH, normalize_embeddings=True)
embedder_sem.warm_up()
retriever_embedding_sem = InMemoryEmbeddingRetriever(document_store=document_store)
semantic_pipeline = Pipeline()
semantic_pipeline.add_component("embedder", embedder_sem)
semantic_pipeline.add_component("retriever_embedding", retriever_embedding_sem)
semantic_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
logger.info(f"Semantic pipeline components: {list(semantic_pipeline.graph.nodes.keys())}")
# Document embedder for reindexing (batch embedding of documents)
embedder_doc = SentenceTransformersDocumentEmbedder(model=MODEL_PATH, normalize_embeddings=True)
embedder_doc.warm_up()
# Ported helpers (all below from app.py)
def search_stories(query, source_filter=None, type_filter=None, search_mode="Both", top_k=1000, min_score=0.2, assignment_filter="all"):
    """
    Search for stories using story-level embeddings (Phase 1 optimization).
    Now searches story documents directly instead of chunks.
    """
    logger.info(f"Searching for query: {query}, source: {source_filter}, type: {type_filter}, mode: {search_mode}, min_score: {min_score}")
    
    # Build filters - force story-level search by default
    filters = {"operator": "AND", "conditions": [
        {"field": "type", "operator": "==", "value": "story"}  # PHASE 1: Only search story-level docs
    ]}
    
    if source_filter and source_filter != "All Sources":
        filters["conditions"].append({"field": "book", "operator": "==", "value": source_filter})
    
    # Note: type_filter (Story/Non-Story) is now handled by default story-level filtering
    # If you need chunk search for commentary in future, add a search_level parameter
    
    logger.debug(f"Applying filters: {filters}")
    filters_param = filters if filters["conditions"] else None
    
    # Run search pipeline
    try:
        if search_mode == "Both":
            results = both_pipeline.run({
                "embedder": {"text": query},
                "retriever_embedding": {"top_k": top_k, "filters": filters_param},
                "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters_param}
            })
            documents = results["joiner"]["documents"]
        elif search_mode == "Keywords":
            results = keyword_pipeline.run({
                "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters_param}
            })
            documents = results["retriever_bm25"]["documents"]
        elif search_mode == "Semantic":
            results = semantic_pipeline.run({
                "embedder": {"text": query},
                "retriever_embedding": {"top_k": top_k, "filters": filters_param}
            })
            documents = results["retriever_embedding"]["documents"]
        elif search_mode == "Exact":
            all_docs = document_store.filter_documents(filters=filters_param)
            documents = []
            query_text = query.strip()
            if ' ' in query_text:
                pattern = re.escape(query_text)
            else:
                pattern = r'\b' + re.escape(query_text) + r'\b'
            for doc in all_docs:
                content = doc.content
                count = len(re.findall(pattern, content, re.IGNORECASE))
                if count > 0:
                    doc.score = count  # Use count as score for sorting by frequency
                    documents.append(doc)
        else:
            raise ValueError(f"Invalid search mode: {search_mode}")
        
        logger.debug(f"Retrieved {len(documents)} story documents")
        if documents:
            logger.info(f"Sample doc meta: {documents[0].meta}")
            logger.info(f"Sample doc score: {documents[0].score}")
    except Exception as e:
        logger.error(f"Search pipeline failed: {e}", exc_info=True)
        return []
    
    # PHASE 1 CHANGE: Process story-level documents directly (no grouping needed)
    stories = []
    for doc in documents:
        try:
            # Check score threshold
            if doc.score <= min_score:
                continue
            
            # Extract story info from document metadata
            title = doc.meta.get("title")
            book_slug = doc.meta.get("book", "unknown")
            
            if not title:
                logger.warning(f"Story document missing title: {doc.meta}")
                continue
            
            # Get book metadata (cached at startup)
            book_info = get_book_metadata(book_slug)
            
            # Build story result
            story_result = {
                "title": title,
                "book_slug": book_slug,
                "pages": doc.meta.get("pages", "Unknown"),
                "keywords": doc.meta.get("keywords", ""),
                "start_char": doc.meta.get("start_char", 0),
                "end_char": doc.meta.get("end_char", 0),
                "score": doc.score,
                **book_info
            }
            
            # Add search_query for Exact mode (for highlighting)
            if search_mode == "Exact":
                story_result["search_query"] = query
            
            stories.append(story_result)
            
        except Exception as e:
            logger.error(f"Error processing story document: {e}", exc_info=True)
            continue
    
    # Sort by score (should already be sorted, but ensure it)
    sorted_results = sorted(stories, key=lambda x: x["score"], reverse=True)
    
    # Add assignment filtering logic
    if assignment_filter and assignment_filter != "all":
        assigned_titles = get_assigned_titles_set()
        if assignment_filter == "assigned":
            sorted_results = [s for s in sorted_results if s['title'] in assigned_titles]
        elif assignment_filter == "unassigned":
            sorted_results = [s for s in sorted_results if s['title'] not in assigned_titles]
        logger.info(f"Filtered to {len(sorted_results)} {assignment_filter} stories")
    
    logger.info(f"Search returned {len(sorted_results)} story results for query: '{query}'")
    if sorted_results:
        logger.info(f"Top result: '{sorted_results[0]['title']}' | Score: {sorted_results[0]['score']:.3f}")
    
    return sorted_results
def render_md_with_scroll_and_highlight(book_slug, start_char, end_char, page, search_query=None):
    full_md = load_full_md(book_slug)
    try:
        logger.debug(f"Rendering MD for {book_slug} with start_char={start_char}, end_char={end_char}, page={page}")
        # Step 1: Adjust for HTML escaping (< and >)
        escape_pattern = r'[<>]'
        escape_matches = list(re.finditer(escape_pattern, full_md))
        def get_escape_delta(pos):
            delta = 0
            for m in escape_matches:
                if m.start() < pos:
                    delta += 3 # < or > adds 3 characters
            return delta
        escaped_start = start_char + get_escape_delta(start_char)
        escaped_end = end_char + get_escape_delta(end_char)
        # Escape the MD
        escaped_md = full_md.replace('<', '&lt;').replace('>', '&gt;')
        # Step 2: Adjust for anchor insertions on escaped_md
        anchor_pattern = r'\\?\[\s*Page\s*(\d+)\s*\\?\]'
        anchor_matches = list(re.finditer(anchor_pattern, escaped_md, re.IGNORECASE))
        def get_anchor_delta(pos):
            delta = 0
            for m in anchor_matches:
                if m.start() < pos:
                    page_num = m.group(1)
                    replacement = f'<div id="page-{page_num}">[Page {page_num}]</div>'
                    orig_len = m.end() - m.start()
                    rep_len = len(replacement)
                    delta += rep_len - orig_len
            return delta
        adjusted_start = escaped_start + get_anchor_delta(escaped_start)
        adjusted_end = escaped_end + get_anchor_delta(escaped_end)
        # Add anchors
        def replace_anchor(match):
            page_num = match.group(1)
            return f'<div id="page-{page_num}">[Page {page_num}]</div>'
        md_with_anchors = re.sub(anchor_pattern, replace_anchor, escaped_md, flags=re.IGNORECASE)
        # Step 3: If search_query (from Exact mode), add red highlights and adjust deltas
        md_with_red = md_with_anchors
        if search_query:
            search_query = search_query.strip()
            if ' ' in search_query:
                pattern = re.escape(search_query)
            else:
                pattern = r'\b' + re.escape(search_query) + r'\b'
            red_matches = list(re.finditer(pattern, md_with_anchors, re.IGNORECASE))
            def get_red_delta(pos):
                delta = 0
                for m in red_matches:
                    if m.start() < pos:
                        delta += 33 # len('<span style="color: red;"></span>')
                return delta
            adjusted_start += get_red_delta(adjusted_start)
            adjusted_end += get_red_delta(adjusted_end)
            # Apply red highlights
            def replace_red(match):
                return '<span style="color: red;">' + match.group(0) + '</span>'
            md_with_red = re.sub(pattern, replace_red, md_with_anchors, flags=re.IGNORECASE)
        # Highlight story range using adjusted positions with ID for scrolling
        highlighted = (
            md_with_red[:adjusted_start] +
            '<span id="story-highlight" style="background-color: #fbbf24; color: #111827; padding: 2px 4px; border-radius: 3px;">' +
            md_with_red[adjusted_start:adjusted_end] +
            '</span>' +
            md_with_red[adjusted_end:]
        )
        html = f"""
        <div id="book-context-container" style="height: 500px; overflow-y: scroll; font-family: Arial; white-space: pre-wrap; background-color: #1f2937; color: #f3f4f6; padding: 1rem; border-radius: 0.5rem;">{highlighted}</div>
        """
        return html
    except Exception as e:
        logger.error(f"Failed to render MD for {book_slug}: {e}")
        return "Error rendering story."
def render_static_story(story):
    """Render a static story from markdown"""
    book_slug = story['book_slug']
    full_md = load_full_md(book_slug)
    text = full_md[story['start_char']:story['end_char']]
    return text # Frontend already displays metadata in header, so just return the story text
def find_book_slug(title):
    for book_slug in books:
        positions = load_story_positions(book_slug)
        if title in positions:
            return book_slug
    raise ValueError(f"Book not found for title: {title}")
def export_stories(stories, format='md', is_single=True):
    try:
        format = format.lower()
        logger.debug(f"Exporting stories, format={format}, is_single={is_single}")
        content = ""
        for story in stories:
            book_slug = story.get('book_slug')
            if book_slug is None:
                book_slug = find_book_slug(story['title'])
            full_md = load_full_md(book_slug)
            title = story['title']
            pages = story['pages']
            keywords = story['keywords']
            start = story.get('start_char', 0)
            end = story.get('end_char', len(full_md))
            text = full_md[start:end]
            logger.debug(f"Exporting story '{title}' from {book_slug} with slice [{start}:{end}], text length: {len(text)}")
            content += f"# {title}\n\nSource: {book_slug.replace('_', ' ').title()}\nPages: {pages}\nKeywords: {keywords}\n\n{text}\n\n---\n\n"
        base_filename = "export_single" if is_single else "export_list"
        temp_md = f"/tmp/{base_filename}.md"
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(content)
        if format == 'md':
            filepath = temp_md
            mime = 'text/markdown'
            ext = 'md'
        elif format == 'pdf':
            filepath = f"/tmp/{base_filename}.pdf"
            try:
                subprocess.run(['pandoc', temp_md, '-o', filepath], check=True)
            except:
                logger.warning("Pandoc failed; using reportlab fallback.")
                c = canvas.Canvas(filepath, pagesize=letter)
                y = 750
                for line in content.split('\n')[:50]: # Limit for prototype
                    c.drawString(50, y, line[:100])
                    y -= 15
                c.save()
            mime = 'application/pdf'
            ext = 'pdf'
        elif format == 'word':
            filepath = f"/tmp/{base_filename}.docx"
            try:
                subprocess.run(['pandoc', temp_md, '-o', filepath], check=True)
            except:
                logger.warning("Pandoc failed; using python-docx fallback.")
                doc = DocxDocument()
                doc.add_paragraph(content)
                doc.save(filepath)
            mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ext = 'docx'
        else:
            raise ValueError(f"Unsupported format: {format}")
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return {'mime': mime, 'data': data, 'filename': f"{base_filename}.{ext}"}
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return None
def export_updated_jsons(pending_updates):
    try:
        if not pending_updates:
            return ""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for book_slug, updates in pending_updates.items():
                original_positions = load_story_positions(book_slug).copy()
                for title, bounds in updates.items():
                    if title in original_positions:
                        for key, val in bounds.items():
                            original_positions[title][key] = val
                    else:
                        logger.warning(f"Title {title} not found in {book_slug}; skipping update.")
                json_data = json.dumps(original_positions, indent=4, ensure_ascii=False).encode('utf-8')
                zip_file.writestr(f"updated_story_positions_{book_slug}.json", json_data)
        zip_buffer.seek(0)
        data = base64.b64encode(zip_buffer.read()).decode('utf-8')
        data_uri = f"data:application/zip;base64,{data}"
        return f'<a href="{data_uri}" download="updated_story_positions.zip">Download Updated JSONs ZIP</a>'
    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        return "Export failed."
# CATEGORIES dict (ported from HF app.py)
CATEGORIES = {
    "Demonic Activity": {
        "Obsession": {
            "Fear/Anxiety": [],
            "Emotional Guilt": [],
            "Anger": [],
            "Reduction of Voluntariness": []
        },
        "Oppression": {
            "Haunting Vexations": {
                "Poltergeist": [],
                "Shadow People": [],
                "Sleep Paralysis": [],
                "Static People": [],
                "Glimmer Man": [],
                "Flannel Man": []
            },
            "Physical Health Vexations": {
                "Death": [],
                "Bruise": [],
                "Bite Marks": [],
                "Scratches": [],
                "Unexplained Physical Pain": [],
                "Headaches": [],
                "Insomnia": [],
                "Bumps, Cysts, other Protrusions": [],
                "Bone Dislocation": [],
                "Distention of the Stomach": [],
                "Nausea": [],
                "Foul Breath": [],
                "Miscarriages": [],
                "Blocked Conception": [],
                "Sexual Assault": [],
                "Pronounced Sleep Behaviors/Manifestations": [],
                "Minor Morphing": [],
                "Suffocation": [],
                "Choking": [],
                "Serious Physical Injury": []
            },
            "Mental Health Vexations": {
                "Weariness": [],
                "Dreams": [],
                "Depression": [],
                "Anger": [],
                "Emotional/Relational Block": [],
                "Visual Hallucinations": [],
                "Auditory Hallucinations": [],
                "Severe Mental Disorder": []
            },
            "Peripheral Vexations": {
                "Pets": [],
                "Bugs/Pests": [],
                "Financial": [],
                "Occupational": [],
                "Reputational": []
            }
        },
        "Possession": {
            "Speaking a Foreign Language": [],
            "Occult Knowledge": [],
            "Morphing": [],
            "Strength": [],
            "Appearance of Fortunae": {
                "Nails": [],
                "Glass": [],
                "Cloth": [],
                "Other": []
            },
            "Levitation": [],
            "Superhuman Speed": [],
            "Superhuman Agility": [],
            "Gravitas": [],
            "Sustained Unnatural Posture": [],
            "Fasting": [],
            "Secondary Signs": {
                "Repugnance towards Holiness": [],
                "Obscene Thoughts Around Holiness": [],
                "Blocked Prayer": [],
                "Aversion to Scripture": [],
                "Illness around Holiness": [],
                "Aversion to Sacred Names": [],
                "Pain From Holy Items": [],
                "Difficulty in Receiving Sacraments": [],
                "Liturgical Calendar Suffering": [],
                "Chronic Insomnia": [],
                "Affected Dreams": [],
                "Falsified Emotions": [],
                "Speaking in Tongues": [],
                "Possession-Specific Physical Vexation": {
                    "Foul Odor": [],
                    "Drastic Eating Changes": [],
                    "Fluctuation in Body Temperature": [],
                    "Diabolical Incandescence": []
                },
                "Suffering Spirituality": {
                    "Fruitless Self-Satisfaction": [],
                    "Anguish over sins": [],
                    "Spiritual Security": [],
                    "Self-Aggrandizing Behavior": [],
                    "Contempt for little things (spiritual)": [],
                    "Closed towards Spiritual Director": [],
                    "Nonconformity with scripture and tradition": [],
                    "animus delendi (destruction)": []
                }
            }
        }
    },
    "Ghostly Activity": {
        "Family Member/Loved One": {
            "Appearance": [],
            "Voice": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Stranger": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Individual Connected To Place/Person": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Family Pet": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Other Animal": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        }
    },
    "Cryptid": {
        "Canine": {
            "Dogman": [],
            "Werewolf": [],
            "Chupacabra": [],
            "Other": []
        },
        "Avian": {
            "Thunderbird": [],
            "Mothman": [],
            "Other": []
        },
        "Bipedal": {
            "Sasquatch": [],
            "Humanoid": [],
            "Other": []
        },
        "Aquatic": [],
        "Feline": [],
        "Cervidae": {
            "Deer": [],
            "Moose": []
        }
    },
    "Fae": {
        "Fairy": [],
        "Nymph": [],
        "Gnome": [],
        "Other": []
    },
    "Witchcraft": {
        "Flying": [],
        "Levitation": [],
        "Transportation": [],
        "Cursing": [],
        "Hagriding": [],
        "Evil Eye": [],
        "Abduction": {
            "Child": [],
            "Adult": [],
            "Pet": [],
            "Non-Pet Animal": []
        },
        "Physical Harm": [],
        "Physical Harm To Children": [],
        "Herbal/Natural": [],
        "Divination": [],
        "Harm to Crops": [],
        "Harm to Livestock": [],
        "Harm To Pets": [],
        "Sacrificing Children": [],
        "Indoctrinating Children": [],
        "Black Sabbath": [],
        "Ritual": {
            "Black Sabbath": [],
            "Contract with Demon": [],
            "Contract with Another": [],
            "Sacrilegious Baptism": [],
            "Sacrifice": {
                "Sacrificing a Person": {
                    "Sacrificing a Family Member": {
                        "Sacrificing a Parent": [],
                        "Sacrificing a Child": [],
                        "Sacrificing a Sibling": [],
                        "Sacrificing a Grandparent": [],
                        "Sacrificing an Aunt/Uncle": [],
                        "Sacrificing a cousin": [],
                        "Sacrificing a niece/nephew": []
                    },
                    "Sacrificing a Friend": [],
                    "Sacrificing a known associate": [],
                    "Sacrificing a stranger": []
                },
                "Sacrificing an Animal": [],
                "Sacrificing a Family Member": []
            },
            "Rejection of Sacraments": {
                "Rejection of Baptism": [],
                "Rejection of Confirmation": [],
                "Rejection of Confession": [],
                "Rejection of Eucharist": [],
                "Rejection of Marriage": [],
                "Rejection of Holy Orders": []
            }
        }
    },
    "Supernatural Phenomena": {
        "Time Slip": [],
        "Time Loss": []
    }
}
# Helper: Load/save codex_tree.json (pre-populate if empty)
def load_codex_tree_from_json():
    if os.path.exists(codex_tree_path):
        with open(codex_tree_path, "r") as f:
            tree = json.load(f)
    else:
        tree = CATEGORIES.copy()
        def ensure_lists(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    ensure_lists(v)
                else:
                    d[k] = []
        ensure_lists(tree)
        save_codex_tree_to_json(tree)
    return tree
def save_codex_tree_to_json(tree):
    with open(codex_tree_path, "w") as f:
        json.dump(tree, f, indent=4)
def merge_trees(existing_tree, new_tree):
    """Recursively merge two tree structures, preserving stories"""
    if isinstance(existing_tree, dict) and isinstance(new_tree, dict):
        merged = {}
        # Get all keys from both trees
        all_keys = set(existing_tree.keys()) | set(new_tree.keys())
        for key in all_keys:
            existing_val = existing_tree.get(key)
            new_val = new_tree.get(key)
            if existing_val is not None and new_val is not None:
                # Both have values - merge recursively
                merged[key] = merge_trees(existing_val, new_val)
            elif existing_val is not None:
                # Only existing has value
                merged[key] = existing_val
            else:
                # Only new has value
                merged[key] = new_val
        return merged
    elif isinstance(existing_tree, list) and isinstance(new_tree, list):
        # Merge lists (stories) - combine and deduplicate
        combined = list(set(existing_tree + new_tree))
        logger.info(f"Merged story lists: {existing_tree} + {new_tree} = {combined}")
        return combined
    else:
        # Type mismatch or one is empty - prefer the one with actual content
        existing_is_story_list = isinstance(existing_tree, list) and len(existing_tree) > 0
        new_is_story_list = isinstance(new_tree, list) and len(new_tree) > 0
        if existing_is_story_list and not new_is_story_list:
            logger.info(f"Preferring existing story list: {existing_tree} over {new_tree}")
            return existing_tree
        elif new_is_story_list and not existing_is_story_list:
            logger.info(f"Preferring new story list: {new_tree} over {existing_tree}")
            return new_tree
        else:
            # Neither is a story list, or both are empty, or both have content but different types
            # Prefer dicts over empty lists, existing over new for same types
            if isinstance(existing_tree, dict) and isinstance(new_tree, list):
                return existing_tree
            elif isinstance(new_tree, dict) and isinstance(existing_tree, list):
                return new_tree
            else:
                # Same types or both empty - keep existing
                return existing_tree
# Helper functions for loading stories and managing tree
def load_all_stories():
    """Load stories from story_positions.json in each book folder"""
    stories_dict = {}
    for book_slug in os.listdir(books_dir):
        book_path = os.path.join(books_dir, book_slug)
        if os.path.isdir(book_path) and not book_slug.startswith('.'):
            positions = load_story_positions(book_slug)
            for title, details in positions.items():
                stories_dict[title] = {
                    "title": title,
                    "book_slug": book_slug,
                    "pages": details.get("pages", ""),
                    "keywords": ', '.join(details.get("keywords", [])),
                    "start_char": details.get("start_char", 0),
                    "end_char": details.get("end_char", 0)
                }
    logger.info(f"Loaded {len(stories_dict)} stories from story_positions.json across books")
    return stories_dict
def insert_recursive(tree_json, db, parent_id=None):
    """Recursively insert tree nodes into database"""
    for name, value in tree_json.items():
        node = CodexNode(name=name, parent_id=parent_id)
        db.add(node)
        db.flush() # Get ID
        if isinstance(value, list):
            for title in value:
                story = db.query(Story).filter_by(title=title).first()
                if story:
                    db.add(NodeStory(node_id=node.id, story_id=story.id))
        elif isinstance(value, dict):
            insert_recursive(value, db, node.id)
def enrich_stories_with_book_metadata(stories):
    """Add book metadata (title, author, year) to story objects using preloaded cache"""
    enriched = []
    for story in stories:
        enriched_story = story.copy()
        book_slug = story.get('book_slug')
        
        # Use the preloaded cache instead of querying the database
        if book_slug and book_slug in _book_metadata_cache:
            book_meta = _book_metadata_cache[book_slug]
            enriched_story['book_title'] = book_meta.get('book_title', book_slug)
            enriched_story['book_author'] = book_meta.get('book_author', 'Unknown')
            enriched_story['book_year'] = book_meta.get('book_year', '')
        else:
            # Fallback: use book_slug as title if not in cache
            logger.debug(f"Book metadata not found in cache for {book_slug}")
            enriched_story['book_title'] = book_slug.replace('_', ' ').title() if book_slug else 'Unknown'
            enriched_story['book_author'] = 'Unknown'
            enriched_story['book_year'] = ''
        
        enriched.append(enriched_story)
    
    return enriched

def get_stories_at_path(tree, path):
    """Get stories at a given path in the tree - like original app.py"""
    global stories_dict
    logger.info(f"get_stories_at_path called with path: {path}")
    current = tree
    for level in path:
        logger.info(f"Looking for level '{level}' in current keys: {list(current.keys()) if isinstance(current, dict) else type(current)}")
        if level not in current:
            logger.info(f"Level '{level}' not found in tree")
            return []
        current = current[level]
        logger.info(f"Navigated to '{level}', current is now: {type(current)}")
    # Once we reach the target path, collect ALL stories at or below this level
    titles = []
    def recurse(node):
        if isinstance(node, list):
            # Direct list of story titles
            titles.extend(node)
            logger.info(f"Found story list: {node}")
        elif isinstance(node, dict):
            # Check for _stories key
            if '_stories' in node:
                titles.extend(node['_stories'])
                logger.info(f"Found _stories: {node['_stories']}")
            # Recursively search all child nodes
            for key, value in node.items():
                if key != '_stories':
                    recurse(value)
    recurse(current)
    logger.info(f"Total titles collected: {titles}")
    # Resolve to full story objects
    unique_titles = set(titles)
    result = [stories_dict[title] for title in unique_titles if title in stories_dict]
    logger.info(f"Returning {len(result)} stories: {[s['title'] for s in result]}")
    # Enrich with book metadata
    return enrich_stories_with_book_metadata(result)
# ------------------------------------------------------------------ #
# Disk → DB Sync (Heavy Operation)
# ------------------------------------------------------------------ #
def sync_books_from_metadata(db):
    """Sync Book records from stories_meta.json files in book folders.
    Returns count of books synced.
    """
    from datetime import datetime
    
    synced_count = 0
    for folder in os.listdir(books_dir):
        folder_path = os.path.join(books_dir, folder)
        if not os.path.isdir(folder_path) or folder.startswith('.'):
            continue
        
        meta_path = os.path.join(folder_path, "stories_meta.json")
        if not os.path.exists(meta_path):
            logger.debug(f"No stories_meta.json in {folder}")
            continue
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            # Use folder name as canonical slug
            slug = folder
            title = meta.get("book_title", folder.replace('_', ' ').title())
            author = meta.get("book_author", "Unknown")
            year = meta.get("book_year", "")
            
            # Upsert book
            book = db.query(Book).filter_by(slug=slug).first()
            if book:
                book.title = title
                book.author = author
                book.year = year
                book.updated_at = datetime.utcnow()
            else:
                book = Book(
                    slug=slug,
                    title=title,
                    author=author,
                    year=year,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(book)
            db.flush()
            synced_count += 1
            
        except Exception as e:
            logger.error(f"Error syncing book metadata from {meta_path}: {e}")
            continue
    
    return synced_count

def sync_disk_to_db():
    """Heavy operation: Read all story_positions.json files and sync to database.
    Call this only on server startup or explicit reload via /api/reload-stories.
    """
    global stories_dict
    
    logger.info("Starting disk → DB sync...")
    start_time = time.monotonic()
    
    # First, sync book metadata from stories_meta.json files
    if USE_DB and SessionLocal:
        try:
            with SessionLocal() as db:
                from models import Book
                for book_slug in os.listdir(books_dir):
                    book_path = os.path.join(books_dir, book_slug)
                    if os.path.isdir(book_path) and not book_slug.startswith('.'):
                        meta_path = os.path.join(book_path, "stories_meta.json")
                        if os.path.exists(meta_path):
                            try:
                                with open(meta_path, "r", encoding="utf-8") as f:
                                    meta = json.load(f)
                                
                                # Check if book already exists
                                book = db.query(Book).filter_by(slug=book_slug).first()
                                if book:
                                    # Update existing book
                                    book.title = meta.get("book_title", book_slug)
                                    book.author = meta.get("book_author", "Unknown")
                                    book.year = meta.get("book_year", "")
                                else:
                                    # Create new book
                                    book = Book(
                                        slug=book_slug,
                                        title=meta.get("book_title", book_slug),
                                        author=meta.get("book_author", "Unknown"),
                                        year=meta.get("book_year", "")
                                    )
                                    db.add(book)
                                logger.info(f"Synced book metadata for '{book_slug}': {meta.get('book_title')}")
                            except Exception as e:
                                logger.warning(f"Failed to load stories_meta.json for {book_slug}: {e}")
                db.commit()
                logger.info("Book metadata sync complete")
        except Exception as e:
            logger.error(f"Failed to sync book metadata: {e}")
    
    # Load all stories from disk (source of truth)
    disk_stories = load_all_stories()
    stories_dict = disk_stories.copy()
    
    # Write stories_dict.json for consistency
    try:
        with open(stories_dict_path, "w", encoding="utf-8") as f:
            json.dump(stories_dict, f, indent=4, ensure_ascii=False)
        logger.info(f"Updated {stories_dict_path} with {len(stories_dict)} stories")
    except Exception as e:
        logger.error(f"Failed to write stories_dict.json: {e}")
    
    # If DB is enabled, sync disk → DB (upsert)
    if USE_DB and SessionLocal:
        try:
            with SessionLocal() as db:
                # First, sync Book metadata from stories_meta.json files
                books_synced = sync_books_from_metadata(db)
                logger.info(f"Synced {books_synced} books from metadata")
                
                # Build book_slug -> book_id mapping
                book_map = {book.slug: book.id for book in db.query(Book).all()}
                
                existing_story_ids = {s.id for s in db.query(Story).all()}
                
                for title, data in disk_stories.items():
                    story = db.query(Story).filter_by(title=title).first()
                    book_id = book_map.get(data["book_slug"])
                    
                    if story:
                        # Update existing story - preserves NodeStory relationships
                        story.book_slug = data["book_slug"]
                        story.book_id = book_id
                        story.pages = data["pages"]
                        story.keywords = data["keywords"]
                        story.start_char = data["start_char"]
                        story.end_char = data["end_char"]
                    else:
                        # Create new story with book relationship
                        new_story = Story(**data, book_id=book_id)
                        db.add(new_story)
                        db.flush()
                db.commit()
                
                new_story_ids = {s.id for s in db.query(Story).all()}
                added_stories = new_story_ids - existing_story_ids
                
                if added_stories:
                    logger.info(f"Added {len(added_stories)} new stories to DB")
                
                elapsed = time.monotonic() - start_time
                logger.info(f"Synced {len(disk_stories)} stories from disk to DB in {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"DB sync failed: {e}")
    else:
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded {len(disk_stories)} stories from disk (no DB) in {elapsed:.2f}s")

# ------------------------------------------------------------------ #
# Load Codex Tree (Lightweight Operation)
# ------------------------------------------------------------------ #
def load_codex_tree():
    """Lightweight operation: Build tree from database or JSON fallback.
    Does NOT sync from disk - that's done by sync_disk_to_db().
    """
    global stories_dict
    
    logger.info("Building codex tree...")
    start_time = time.monotonic()

    # Fallback if no DB - load from JSON
    if not USE_DB or SessionLocal is None:
        logger.info("Using JSON fallback for codex tree")
        tree = load_codex_tree_from_json()
        
        # Ensure stories_dict is loaded
        if not stories_dict:
            with open(stories_dict_path, "r") as f:
                stories_dict = json.load(f)
        
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded tree from JSON in {elapsed:.2f}s")
        return tree
   
    try:
        with SessionLocal() as db:
            root_nodes = db.query(CodexNode).filter_by(parent_id=None).all()
            if not root_nodes:
                logger.info("No codex nodes in DB - initializing from CATEGORIES")
                tree_json = load_codex_tree_from_json()
                # Insert from JSON
                insert_recursive(tree_json, db)
                db.commit()
                root_nodes = db.query(CodexNode).filter_by(parent_id=None).all()
           
            # Eagerly load all relationships recursively to avoid lazy loading issues
            from sqlalchemy.orm import selectinload
            from models import NodeStory
           
            # Use a recursive strategy to load all nodes with their relationships
            def load_all_nodes_recursive():
                """Load all nodes with their stories and children relationships"""
                # Load all nodes at once with relationships
                all_nodes = db.query(CodexNode).options(
                    selectinload(CodexNode.stories),
                    selectinload(CodexNode.children).selectinload(CodexNode.stories),
                    selectinload(CodexNode.children).selectinload(CodexNode.children).selectinload(CodexNode.stories),
                    selectinload(CodexNode.children).selectinload(CodexNode.children).selectinload(CodexNode.children).selectinload(CodexNode.stories)
                ).all()
               
                # Create a lookup dict for fast access
                nodes_by_id = {node.id: node for node in all_nodes}
               
                # Rebuild parent-child relationships
                for node in all_nodes:
                    if node.parent_id and node.parent_id in nodes_by_id:
                        parent = nodes_by_id[node.parent_id]
                        if node not in parent.children:
                            parent.children.append(node)
                            logger.debug(f"Added {node.name} as child of {parent.name}")
               
                # Debug: Check if Fear/Anxiety is in the tree
                fear_node = next((n for n in all_nodes if n.name == 'Fear/Anxiety'), None)
                if fear_node:
                    # Check NodeStory relationships directly
                    node_story_count = db.query(NodeStory).filter_by(node_id=fear_node.id).count()
                    node_stories = db.query(NodeStory).filter_by(node_id=fear_node.id).all()
                    story_ids = [ns.story_id for ns in node_stories]
                    logger.info(f"FEAR/ANXIETY FOUND: id={fear_node.id}, parent_id={fear_node.parent_id}")
                    logger.info(f"FEAR/ANXIETY NodeStory count: {node_story_count}, story_ids: {story_ids}")
                    logger.info(f"FEAR/ANXIETY stories relationship: {[s.title for s in fear_node.stories] if fear_node.stories else []}")
                    logger.info(f"FEAR/ANXIETY children: {[c.name for c in fear_node.children] if fear_node.children else []}")
                    if fear_node.parent_id:
                        parent_node = nodes_by_id.get(fear_node.parent_id)
                        if parent_node:
                            logger.info(f"FEAR/ANXIETY PARENT: {parent_node.name}, children={[c.name for c in parent_node.children] if parent_node.children else []}")
                else:
                    logger.warning("FEAR/ANXIETY NODE NOT FOUND IN DATABASE!")
               
                return [node for node in all_nodes if node.parent_id is None]
           
            root_nodes_with_relations = load_all_nodes_recursive()
           
            def build_tree(node):
                """Build tree structure including stories from database relationships"""
                # Special logging for Fear/Anxiety
                is_fear_anxiety = node.name == 'Fear/Anxiety'
                if is_fear_anxiety:
                    logger.info(f"=== BUILD_TREE CALLED FOR FEAR/ANXIETY ===")
                    logger.info(f"Node object: id={node.id}, name={node.name}, parent_id={getattr(node, 'parent_id', None)}")
                    logger.info(f"Has stories attr: {hasattr(node, 'stories')}")
                    logger.info(f"Node.stories type: {type(node.stories) if hasattr(node, 'stories') else 'N/A'}")
               
                try:
                    # Get stories for this node (should be eagerly loaded)
                    # Debug: Check what we actually have
                    if is_fear_anxiety:
                        logger.info(f"FEAR/ANXIETY DEBUG: node.stories type: {type(node.stories)}, value: {node.stories}")
                        logger.info(f"FEAR/ANXIETY DEBUG: hasattr stories: {hasattr(node, 'stories')}")
                        logger.info(f"FEAR/ANXIETY DEBUG: node.stories bool: {bool(node.stories) if hasattr(node, 'stories') else 'N/A'}")
                        # Try to access it
                        try:
                            stories_list = list(node.stories) if hasattr(node, 'stories') else []
                            logger.info(f"FEAR/ANXIETY DEBUG: list(node.stories): {stories_list}")
                        except Exception as e:
                            logger.error(f"FEAR/ANXIETY DEBUG: Error accessing node.stories: {e}")
                   
                    story_titles = [s.title for s in node.stories] if hasattr(node, 'stories') and node.stories else []
                    if is_fear_anxiety:
                        logger.info(f"FEAR/ANXIETY: story_titles after extraction: {story_titles}")
                    if story_titles:
                        logger.info(f"Building tree for node '{node.name}' with {len(story_titles)} stories: {story_titles}")
                   
                    # If node has stories and no children, use list format
                    # Otherwise, use dict with _stories key
                    children_list = list(node.children) if hasattr(node, 'children') and node.children else []
                    if is_fear_anxiety:
                        logger.info(f"FEAR/ANXIETY: children_list: {[c.name for c in children_list]}")
                   
                    logger.info(f"Node '{node.name}': {len(story_titles)} stories, {len(children_list)} children")
                except Exception as e:
                    logger.error(f"Error in build_tree for node '{node.name}': {e}", exc_info=True)
                    return {node.name: {}}
               
                if story_titles and len(children_list) == 0:
                    # Leaf node with stories - use list format
                    tree = {node.name: story_titles}
                    logger.info(f"Returning leaf node format for '{node.name}': {tree}")
                else:
                    # Node with children or intermediate node
                    tree = {node.name: {}}
                    if story_titles:
                        tree[node.name]['_stories'] = story_titles
                        logger.info(f"Added _stories to '{node.name}': {tree[node.name]}")
                   
                    # Add children (relationships should already be loaded)
                    for child in children_list:
                        child_tree = build_tree(child)
                        logger.info(f"Merging child '{child.name}' into '{node.name}': {child_tree}")
                       
                        # Do NOT merge duplicate keys across different parent contexts
                        # Each node should exist under its correct parent path only
                        # The database should not have duplicate names under the same parent
                        for child_key, child_value in child_tree.items():
                            if child_key in tree[node.name]:
                                logger.error(f"Unexpected duplicate child '{child_key}' found under '{node.name}'. This indicates a database integrity issue. Skipping child: {child_value}")
                                continue
                            # Normal merge for new keys
                            tree[node.name][child_key] = child_value
                   
                    # Special check for nodes we know have stories
                    if node.name == 'Fear/Anxiety':
                        logger.info(f"FEAR/ANXIETY DEBUG: tree={tree}, story_titles={story_titles}, children_list={[c.name for c in children_list]}")
                        logger.info(f"FEAR/ANXIETY DEBUG: tree[node.name]={tree[node.name]}")
               
                logger.info(f"Final tree for '{node.name}': {tree}")
                return tree
           
            tree = {}
            for root in root_nodes_with_relations:
                root_tree = build_tree(root)
                logger.debug(f"Merging root '{root.name}' into tree: {root_tree}")
                # Merge root trees properly, handling conflicts
                for root_key, root_value in root_tree.items():
                    if root_key in tree:
                        logger.warning(f"Root conflict for '{root_key}', merging subtrees")
                        tree[root_key] = merge_trees(tree[root_key], root_value)
                    else:
                        tree[root_key] = root_value
           
            # Log summary of tree structure for debugging
            def count_stories_in_tree(t):
                count = 0
                if isinstance(t, dict):
                    for k, v in t.items():
                        if k == '_stories' and isinstance(v, list):
                            count += len(v)
                            logger.debug(f"Found {len(v)} stories in _stories: {v}")
                        elif isinstance(v, (dict, list)):
                            count += count_stories_in_tree(v)
                elif isinstance(t, list):
                    count += len(t)
                    logger.debug(f"Found {len(t)} stories in list: {t}")
                return count
           
            total_stories = count_stories_in_tree(tree)
            logger.info(f"Loaded codex tree from database with {total_stories} total story assignments")
           
            # Also log the actual tree structure for the node we know has stories
            if 'Demonic Activity' in tree:
                da = tree['Demonic Activity']
                logger.info(f"Demonic Activity structure type: {type(da)}, keys: {list(da.keys()) if isinstance(da, dict) else 'N/A'}")
                if isinstance(da, dict) and 'Obsession' in da:
                    obs = da['Obsession']
                    logger.info(f"Obsession structure type: {type(obs)}, keys: {list(obs.keys()) if isinstance(obs, dict) else 'N/A'}")
                    if isinstance(obs, dict) and 'Fear/Anxiety' in obs:
                        fear = obs['Fear/Anxiety']
                        logger.info(f"Fear/Anxiety structure: {fear} (type: {type(fear)}, is_list: {isinstance(fear, list)}, is_dict: {isinstance(fear, dict)})")
                        if isinstance(fear, dict):
                            logger.info(f"Fear/Anxiety dict keys: {list(fear.keys())}")
                            if '_stories' in fear:
                                logger.info(f"Fear/Anxiety _stories: {fear['_stories']}")
                    elif isinstance(obs, dict):
                        logger.info(f"Obsession keys but no Fear/Anxiety: {list(obs.keys())}")
                elif isinstance(da, dict):
                    logger.info(f"Demonic Activity is dict but no Obsession: {list(da.keys())}")
           
            # Save tree to JSON for backup/consistency
            save_codex_tree_to_json(tree)
            
            elapsed = time.monotonic() - start_time
            logger.info(f"Built tree from DB with {total_stories} assignments in {elapsed:.2f}s")
            return tree
    except Exception as e:
        logger.error(f"Error loading codex tree from database: {e}. Falling back to JSON.")
        tree = load_codex_tree_from_json()
        
        # Ensure stories_dict is loaded
        if not stories_dict:
            with open(stories_dict_path, "r") as f:
                stories_dict = json.load(f)
        
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded tree from JSON fallback in {elapsed:.2f}s")
        return tree
def save_codex_tree(tree):
    """Save codex tree to JSON file and database (if available), optionally to HuggingFace"""
    global stories_dict
    os.makedirs(data_dir, exist_ok=True)
    
    logger.info("Saving codex tree...")
   
    # Always save to JSON (for fallback and local development)
    save_codex_tree_to_json(tree)
   
    # Also save stories_dict if it exists
    if stories_dict:
        with open(stories_dict_path, "w") as f:
            json.dump(stories_dict, f, indent=4)
   
    # Save to database if available
    if USE_DB and SessionLocal:
        try:
            with SessionLocal() as db:
                from models import CodexNode, NodeStory, Story
               
                def save_tree_to_db(node_dict, parent_id=None, path=[]):
                    """Recursively save tree structure to database"""
                    for name, value in node_dict.items():
                        if name == '_stories':
                            continue
                       
                        # Find or create node
                        query = db.query(CodexNode).filter_by(name=name)
                        if parent_id:
                            query = query.filter_by(parent_id=parent_id)
                        else:
                            query = query.filter_by(parent_id=None)
                        node = query.first()
                       
                        if not node:
                            node = CodexNode(name=name, parent_id=parent_id)
                            db.add(node)
                            db.flush() # Get ID
                       
                        # Get current stories for this node from database - query fresh to avoid stale relationships
                        from sqlalchemy.orm import selectinload
                        fresh_node = db.query(CodexNode).options(
                            selectinload(CodexNode.stories)
                        ).filter_by(id=node.id).first()
                        current_story_ids = {s.id for s in fresh_node.stories} if fresh_node and fresh_node.stories else set()
                        expected_titles = set()
                       
                        # Handle stories at this node
                        if isinstance(value, list):
                            # Leaf node with stories (list format)
                            expected_titles = set(value)
                        elif isinstance(value, dict):
                            # Check for _stories key (intermediate node with stories)
                            if '_stories' in value:
                                expected_titles = set(value['_stories'])
                       
                        # Update relationships: add missing, remove extra
                        for title in expected_titles:
                            story = db.query(Story).filter_by(title=title).first()
                            if story:
                                if story.id not in current_story_ids:
                                    # Add relationship
                                    db.add(NodeStory(node_id=node.id, story_id=story.id))
                                    logger.info(f"Added story '{title}' to node '{name}' (node_id={node.id}, story_id={story.id})")
                            else:
                                logger.warning(f"Story '{title}' not found in database, skipping assignment to '{name}'")
                       
                        # Flush to ensure relationships are persisted
                        db.flush()
                       
                        # Verify relationships were actually created by querying NodeStory directly
                        if expected_titles:
                            node_story_count = db.query(NodeStory).filter_by(node_id=node.id).count()
                            logger.info(f"NodeStory records for node '{name}' (id={node.id}): {node_story_count}")
                           
                            # Log current state after update - query fresh with eager loading
                            from sqlalchemy.orm import selectinload
                            # Expire the node to force a fresh load
                            db.expire(node, ['stories'])
                            updated_node = db.query(CodexNode).options(
                                selectinload(CodexNode.stories)
                            ).filter_by(id=node.id).first()
                            actual_titles = [s.title for s in updated_node.stories] if updated_node.stories else []
                            logger.info(f"Node '{name}' now has {len(actual_titles)} stories: {actual_titles}")
                            if len(actual_titles) != len(expected_titles):
                                logger.warning(f"Mismatch: expected {len(expected_titles)} stories but found {len(actual_titles)}")
                                # Debug: list all NodeStory records for this node
                                all_node_stories = db.query(NodeStory).filter_by(node_id=node.id).all()
                                logger.warning(f"NodeStory records: {[(ns.node_id, ns.story_id) for ns in all_node_stories]}")
                       
                        # DON'T remove relationships - only add them
                        # This prevents us from deleting relationships that were added directly to the database
                        # but aren't yet in the in-memory tree structure
                        # Removal should be done explicitly via the remove-category endpoint
                        # if expected_titles and 'updated_node' in locals():
                        # for story in updated_node.stories:
                        # if story.title not in expected_titles:
                        # db.query(NodeStory).filter_by(
                        # node_id=node.id, story_id=story.id
                        # ).delete()
                        # logger.info(f"Removed story '{story.title}' from node '{name}'")
                       
                        # Recursively process children
                        if isinstance(value, dict):
                            save_tree_to_db(value, node.id, path + [name])
               
                save_tree_to_db(tree)
                db.commit()
                logger.info("Saved codex tree to database")
        except Exception as e:
            logger.error(f"Error saving codex tree to database: {e}")
            # Continue to save JSON even if DB save fails
    
    # Invalidate cache after saving
    invalidate_cache()
    logger.info("Cache invalidated after saving codex tree")
   
    # Optional auto-commit to HuggingFace
    token = os.getenv("HF_TOKEN")
    if token:
        try:
            api = HfApi(token=token)
            api.upload_file(
                path_or_fileobj=codex_tree_path,
                path_in_repo=codex_tree_path,
                repo_id="hetzerdj/preternatural-text-ui",
                repo_type="space"
            )
            if stories_dict:
                api.upload_file(
                    path_or_fileobj=stories_dict_path,
                    path_in_repo=stories_dict_path,
                    repo_id="hetzerdj/preternatural-text-ui",
                    repo_type="space"
                )
            logger.info("Auto-committed codex_tree.json and stories_dict.json to HF repo")
        except Exception as e:
            logger.error(f"Auto-commit failed: {e}")
    else:
        logger.info("HF_TOKEN not set; changes saved locally only")
def assign_to_path(tree, path, story):
    """Assign story to path in tree"""
    global stories_dict
    title = story['title']
    # Store full details once
    if title not in stories_dict:
        stories_dict[title] = story
    current = tree
    for level in path[:-1]:
        if level not in current:
            current[level] = {}
        if not isinstance(current[level], dict):
            current[level] = {'_stories': current[level]}
        current = current[level]
    leaf = path[-1]
    if leaf not in current:
        current[leaf] = []
    leaf_val = current[leaf]
    if isinstance(leaf_val, list):
        if title not in leaf_val:
            leaf_val.append(title)
    elif isinstance(leaf_val, dict):
        if '_stories' not in leaf_val:
            leaf_val['_stories'] = []
        if title not in leaf_val['_stories']:
            leaf_val['_stories'].append(title)
    else:
        raise ValueError("Invalid tree structure")
    return tree
def remove_from_path(tree, path, title):
    """Remove story from path in tree"""
    current = tree
    for level in path[:-1]:
        if level not in current:
            return tree
        current = current[level]
    leaf = path[-1]
    if leaf in current:
        leaf_val = current[leaf]
        if isinstance(leaf_val, list) and title in leaf_val:
            leaf_val.remove(title)
        elif isinstance(leaf_val, dict) and '_stories' in leaf_val and title in leaf_val['_stories']:
            leaf_val['_stories'].remove(title)
    return tree
def find_paths_for_title(tree, title, current_path=None, paths=None):
    """Find all paths for a title in the tree"""
    if current_path is None:
        current_path = []
    if paths is None:
        paths = []
    if isinstance(tree, dict):
        if '_stories' in tree and title in tree['_stories']:
            paths.append(current_path[:])
        for key, value in tree.items():
            if key != '_stories':
                find_paths_for_title(value, title, current_path + [key], paths)
    elif isinstance(tree, list):
        if title in tree:
            paths.append(current_path[:])
    return paths

# ------------------------------------------------------------------ #
# Cache for assigned story titles (set of strings)
# ------------------------------------------------------------------ #
_assigned_titles_cache = None

def get_assigned_titles_set():
    """Get cached set of assigned story titles, building if needed."""
    global _assigned_titles_cache
    if _assigned_titles_cache is None:
        rebuild_assigned_titles_cache()
    return _assigned_titles_cache

def rebuild_assigned_titles_cache():
    """Rebuild the cache of assigned story titles by walking the codex tree."""
    global _assigned_titles_cache
    tree = get_cached_tree()
    assigned = set()
    
    def walk(node):
        if isinstance(node, dict):
            if "_stories" in node:
                assigned.update(node["_stories"])
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            assigned.update(node)
    
    walk(tree)
    _assigned_titles_cache = assigned
    logger.info(f"Rebuilt assigned titles cache with {len(assigned)} titles")

def clear_assigned_titles_cache():
    """Clear the assigned titles cache."""
    global _assigned_titles_cache
    _assigned_titles_cache = None
    logger.debug("Cleared assigned titles cache")

# ------------------------------------------------------------------ #
# Pending Stories Queue Management
# ------------------------------------------------------------------ #
pending_stories_path = os.path.join(data_dir, "pending_stories.json")

def load_pending_stories():
    """Load pending stories from disk"""
    if os.path.exists(pending_stories_path):
        try:
            with open(pending_stories_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pending_stories.json: {e}")
            return []
    return []

def save_pending_stories(pending_stories):
    """Save pending stories to disk"""
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pending_stories_path, "w", encoding="utf-8") as f:
            json.dump(pending_stories, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(pending_stories)} pending stories")
        return True
    except Exception as e:
        logger.error(f"Failed to save pending_stories.json: {e}")
        return False

def check_story_overlap(book_slug, new_start, new_end, exclude_title=None):
    """
    Check if new story overlaps with existing stories
    Returns: (has_overlap, overlapping_stories)
    """
    positions = load_story_positions(book_slug)
    overlaps = []
    
    for title, pos in positions.items():
        if title == exclude_title:
            continue
            
        existing_start = pos.get("start_char", -1)
        existing_end = pos.get("end_char", -1)
        
        if existing_start == -1 or existing_end == -1:
            continue
        
        # Check for overlap: two ranges overlap if one doesn't end before the other starts
        if not (new_end <= existing_start or new_start >= existing_end):
            overlap_size = min(new_end, existing_end) - max(new_start, existing_start)
            overlap_percent = (overlap_size / (new_end - new_start)) * 100
            
            overlaps.append({
                "title": title,
                "overlap_chars": overlap_size,
                "overlap_percent": round(overlap_percent, 2)
            })
    
    return len(overlaps) > 0, overlaps