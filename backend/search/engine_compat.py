# backend/search/engine_compat.py
"""
Compatibility layer for transitioning from Haystack to Direct Search.

This module provides Haystack-compatible interfaces using the new
Direct FAISS + SQLite search engine underneath.

Usage:
    # Old code still works:
    from search import document_store, both_pipeline
    results = search_stories(query="test", search_mode="Both")
    
    # But now uses the faster Direct engine underneath
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np

from state import app_state
from .models import StoryDocument
from .engine import SearchEngine, init_search_engine, get_search_engine

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Document Store Compatibility Wrapper
# ------------------------------------------------------------------ #
class DocumentStoreCompat:
    """
    Compatibility wrapper that mimics Haystack's InMemoryDocumentStore API.
    
    Wraps the new SearchEngine to provide backward-compatible methods:
    - count_documents()
    - filter_documents(filters)
    - write_documents(docs)
    - delete_documents(doc_ids)
    - save_to_disk(path)
    """
    
    def __init__(self, search_engine: SearchEngine):
        self._engine = search_engine
    
    def count_documents(self) -> int:
        """Return total document count."""
        return self._engine.document_count
    
    def filter_documents(self, filters: Optional[Dict] = None) -> List[Any]:
        """
        Filter documents by metadata.
        
        Note: This is a simplified implementation that doesn't support
        the full Haystack filter syntax. For complex filters, the results
        may differ from Haystack.
        """
        # For now, return an empty list as we don't store full documents
        # This is mainly used for iteration which we should avoid
        logger.warning("filter_documents() called - consider using search() instead")
        return []
    
    def write_documents(self, docs: List[Any]) -> int:
        """
        Write documents to the store.
        
        Accepts either Haystack Document objects or StoryDocument objects.
        """
        story_docs = []
        for doc in docs:
            if isinstance(doc, StoryDocument):
                story_docs.append(doc)
            else:
                # Assume Haystack Document
                story_docs.append(StoryDocument.from_haystack_doc(doc))
        
        return self._engine.add_documents(story_docs)
    
    def delete_documents(self, doc_ids: List[str]) -> None:
        """Delete documents by ID."""
        for doc_id in doc_ids:
            self._engine.delete_document(doc_id)
    
    def save_to_disk(self, path: str) -> None:
        """Save indices to disk."""
        self._engine.save()


# ------------------------------------------------------------------ #
# Pipeline Compatibility Classes
# ------------------------------------------------------------------ #
class PipelineCompat:
    """
    Compatibility class that mimics Haystack Pipeline.run() interface.
    
    Wraps the new SearchEngine to accept Haystack-style run() calls.
    """
    
    def __init__(self, engine: SearchEngine, mode: str):
        self._engine = engine
        self._mode = mode  # "hybrid", "semantic", "keyword"
    
    def run(self, inputs: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Run the pipeline with Haystack-style inputs.
        
        For hybrid:
            {"embedder": {"text": query},
             "retriever_embedding": {"top_k": N, "filters": {...}},
             "retriever_bm25": {"query": query, "top_k": N, "filters": {...}}}
        
        For semantic:
            {"embedder": {"text": query},
             "retriever_embedding": {"top_k": N, "filters": {...}}}
        
        For keyword:
            {"retriever_bm25": {"query": query, "top_k": N, "filters": {...}}}
        """
        # Extract query
        query = None
        top_k = 100
        book_filter = None
        
        if "embedder" in inputs:
            query = inputs["embedder"].get("text", "")
        
        if "retriever_bm25" in inputs:
            if not query:
                query = inputs["retriever_bm25"].get("query", "")
            retriever_inputs = inputs["retriever_bm25"]
            top_k = retriever_inputs.get("top_k", top_k)
            filters = retriever_inputs.get("filters")
            if filters:
                book_filter = self._extract_book_filter(filters)
        
        if "retriever_embedding" in inputs:
            retriever_inputs = inputs["retriever_embedding"]
            top_k = retriever_inputs.get("top_k", top_k)
            filters = retriever_inputs.get("filters")
            if filters:
                book_filter = self._extract_book_filter(filters)
        
        # Run search
        results = self._engine.search(
            query=query,
            mode=self._mode,
            top_k=top_k,
            book_filter=book_filter
        )
        
        # Convert to Haystack-style output
        # Create mock Document objects with necessary attributes
        documents = []
        for result in results:
            doc = type('Document', (), {
                'id': f"{result['book_slug']}_{hash(result['title'])}",
                'content': '',  # We don't store content
                'meta': {
                    'title': result['title'],
                    'book': result['book_slug'],
                    'pages': result['pages'],
                    'keywords': result['keywords'],
                    'start_char': result['start_char'],
                    'end_char': result['end_char'],
                    'type': 'story',
                },
                'score': result['score'],
                'embedding': None,
            })()
            documents.append(doc)
        
        # Return in Haystack pipeline output format
        if self._mode == "hybrid":
            return {"joiner": {"documents": documents}}
        elif self._mode == "semantic":
            return {"retriever_embedding": {"documents": documents}}
        else:  # keyword
            return {"retriever_bm25": {"documents": documents}}
    
    def _extract_book_filter(self, filters: Dict) -> Optional[str]:
        """Extract book filter from Haystack filter dict."""
        if not filters:
            return None
        
        conditions = filters.get("conditions", [])
        for cond in conditions:
            field = cond.get("field", "")
            if field in ("book", "meta.book"):
                return cond.get("value")
        
        return None


# ------------------------------------------------------------------ #
# Document Embedder Compatibility
# ------------------------------------------------------------------ #
class DocumentEmbedderCompat:
    """
    Compatibility wrapper for SentenceTransformersDocumentEmbedder.
    
    Provides:
    - warm_up()
    - run(documents) -> {"documents": [...with embeddings...]}
    """
    
    def __init__(self, engine: SearchEngine):
        self._engine = engine
    
    def warm_up(self) -> None:
        """Pre-load the embedding model."""
        self._engine.warm_up()
    
    def run(self, documents: List[Any]) -> Dict[str, List[Any]]:
        """
        Embed documents and return them with embeddings attached.
        
        Args:
            documents: List of Haystack Document objects
        
        Returns:
            {"documents": [...with embedding attribute set...]}
        """
        # Extract texts
        texts = [doc.content for doc in documents]
        
        # Embed
        embeddings = self._engine.embed_documents(texts)
        
        # Attach embeddings to documents
        for doc, embedding in zip(documents, embeddings):
            # Convert to list for Haystack compatibility
            doc.embedding = embedding.tolist()
        
        return {"documents": documents}


# ------------------------------------------------------------------ #
# Global Initialization
# ------------------------------------------------------------------ #
_initialized = False
_document_store: Optional[DocumentStoreCompat] = None
_both_pipeline: Optional[PipelineCompat] = None
_keyword_pipeline: Optional[PipelineCompat] = None
_semantic_pipeline: Optional[PipelineCompat] = None
_embedder_doc: Optional[DocumentEmbedderCompat] = None


def initialize_search_engine():
    """
    Initialize the Direct search engine and compatibility wrappers.
    
    This replaces the Haystack pipeline initialization.
    
    Environment variables:
        ENABLE_RERANKER: Set to "true" to enable cross-encoder reranking
        RERANKER_MODEL: Cross-encoder model name (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
    """
    global _initialized, _document_store, _both_pipeline, _keyword_pipeline
    global _semantic_pipeline, _embedder_doc
    
    if _initialized:
        return
    
    logger.info("Initializing Direct FAISS + SQLite search engine...")
    
    # Determine model path (local or HuggingFace)
    backend_dir = Path(__file__).parent.parent
    local_model = backend_dir / "models" / "bge-large-en-v1.5"
    model_path = str(local_model) if local_model.exists() else "BAAI/bge-large-en-v1.5"
    
    # Check if reranking is enabled (now defaults to TRUE for better precision)
    enable_reranker = os.environ.get("ENABLE_RERANKER", "true").lower() == "true"
    reranker_model = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    if enable_reranker:
        logger.info(f"Cross-encoder reranking ENABLED with model: {reranker_model}")
    
    # Initialize engine
    data_dir = str(app_state.data_dir)
    engine = init_search_engine(
        data_dir=data_dir,
        model_path=model_path,
        enable_reranker=enable_reranker,
        reranker_model=reranker_model
    )
    
    # Create compatibility wrappers
    _document_store = DocumentStoreCompat(engine)
    _both_pipeline = PipelineCompat(engine, "hybrid")
    _keyword_pipeline = PipelineCompat(engine, "keyword")
    _semantic_pipeline = PipelineCompat(engine, "semantic")
    _embedder_doc = DocumentEmbedderCompat(engine)
    
    # Store in app_state for other modules
    app_state.document_store = _document_store
    app_state.MODEL_PATH = model_path
    app_state.both_pipeline = _both_pipeline
    app_state.keyword_pipeline = _keyword_pipeline
    app_state.semantic_pipeline = _semantic_pipeline
    app_state.embedder_doc = _embedder_doc
    
    _initialized = True
    logger.info(f"Direct search engine initialized: {engine.document_count} documents")


def get_document_store() -> DocumentStoreCompat:
    """Get the document store (initializes if needed)."""
    if not _initialized:
        initialize_search_engine()
    return _document_store


def get_both_pipeline() -> PipelineCompat:
    """Get the hybrid search pipeline."""
    if not _initialized:
        initialize_search_engine()
    return _both_pipeline


def get_keyword_pipeline() -> PipelineCompat:
    """Get the keyword-only search pipeline."""
    if not _initialized:
        initialize_search_engine()
    return _keyword_pipeline


def get_semantic_pipeline() -> PipelineCompat:
    """Get the semantic-only search pipeline."""
    if not _initialized:
        initialize_search_engine()
    return _semantic_pipeline


def get_embedder_doc() -> DocumentEmbedderCompat:
    """Get the document embedder."""
    if not _initialized:
        initialize_search_engine()
    return _embedder_doc


def get_model_path() -> str:
    """Get the embedding model path."""
    if not _initialized:
        initialize_search_engine()
    return app_state.MODEL_PATH
