# backend/search/pipelines.py
"""
Haystack pipeline initialization and document store management.

This module initializes:
- InMemoryDocumentStore from disk
- Text embedders (for query embedding)
- Document embedder (for indexing new stories)
- Retrievers (embedding and BM25)
- Search pipelines (hybrid, semantic, keyword)
"""

import os
import logging
from collections import Counter
import numpy as np

from haystack import Pipeline
from haystack.components.embedders import (
    SentenceTransformersTextEmbedder,
    SentenceTransformersDocumentEmbedder,
)
from haystack.components.retrievers.in_memory import (
    InMemoryEmbeddingRetriever,
    InMemoryBM25Retriever,
)
from haystack.components.joiners import DocumentJoiner
from haystack.document_stores.in_memory import InMemoryDocumentStore

from state import app_state

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Model Path
# ------------------------------------------------------------------ #
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "bge-large-en-v1.5")
MODEL_PATH = MODEL_DIR if os.path.exists(MODEL_DIR) else "BAAI/bge-large-en-v1.5"

# ------------------------------------------------------------------ #
# Document Store Loading
# ------------------------------------------------------------------ #
document_store = None

if os.path.exists(app_state.document_store_path):
    logger.info("Loading document store from JSON...")
    try:
        document_store = InMemoryDocumentStore.load_from_disk(app_state.document_store_path)
        logger.info(f"Loaded {document_store.count_documents()} documents")
        
        loaded_docs = document_store.filter_documents({})
        doc_types = Counter(doc.meta.get("type", "unknown") for doc in loaded_docs)
        
        # Log sample for debugging
        sample_ids = [doc.id for doc in loaded_docs[:3]]
        sample_metadata = [doc.meta for doc in loaded_docs[:3]]
        sample_content = [doc.content[:50] for doc in loaded_docs[:3]]
        logger.info(f"Document types: {dict(doc_types)}")
        logger.debug(f"Sample IDs: {sample_ids}")
        logger.debug(f"Sample Metadata: {sample_metadata}")
        logger.debug(f"Sample Content: {sample_content}")
        
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
        
        has_embeddings = any(
            doc.embedding is not None and len(doc.embedding) == 1024
            for doc in loaded_docs
        )
        logger.info(f"Documents have valid embeddings: {has_embeddings}")
        
    except Exception as e:
        logger.error(f"Failed to load document store: {e}. Creating new empty document store.")
        document_store = InMemoryDocumentStore()
else:
    logger.error("document_store.json not found.")
    document_store = InMemoryDocumentStore()

# Store reference in app_state for other modules
app_state.document_store = document_store

# ------------------------------------------------------------------ #
# Pipeline Setup
# ------------------------------------------------------------------ #
logger.debug("Setting up Haystack pipelines...")

# Hybrid pipeline (semantic + keyword)
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

# Keyword-only pipeline
retriever_bm25_key = InMemoryBM25Retriever(document_store=document_store)
keyword_pipeline = Pipeline()
keyword_pipeline.add_component("retriever_bm25", retriever_bm25_key)
logger.info(f"Keyword pipeline components: {list(keyword_pipeline.graph.nodes.keys())}")

# Semantic-only pipeline - needs its own embedder instance (Haystack limitation)
# but we can skip warm_up() since model is already cached from embedder_both
embedder_sem = SentenceTransformersTextEmbedder(model=MODEL_PATH, normalize_embeddings=True)
embedder_sem.warm_up()  # Fast since model already in memory/disk cache

retriever_embedding_sem = InMemoryEmbeddingRetriever(document_store=document_store)

semantic_pipeline = Pipeline()
semantic_pipeline.add_component("embedder", embedder_sem)
semantic_pipeline.add_component("retriever_embedding", retriever_embedding_sem)
semantic_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
logger.info(f"Semantic pipeline components: {list(semantic_pipeline.graph.nodes.keys())}")

# Document embedder for indexing new stories
embedder_doc = SentenceTransformersDocumentEmbedder(model=MODEL_PATH, normalize_embeddings=True)
embedder_doc.warm_up()
logger.info("Document embedder initialized for add-story feature")

# Store pipelines in app_state for reference
app_state.MODEL_PATH = MODEL_PATH
app_state.both_pipeline = both_pipeline
app_state.keyword_pipeline = keyword_pipeline
app_state.semantic_pipeline = semantic_pipeline
app_state.embedder_doc = embedder_doc
