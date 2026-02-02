# backend/search/engine.py
"""
Unified search engine combining FAISS (semantic) + FTS5 (keyword) + RRF fusion.

This module provides the main SearchEngine class that:
- Loads embeddings from FAISS for semantic search
- Uses SQLite FTS5 for BM25 keyword search
- Combines results using Reciprocal Rank Fusion (RRF)
- Optionally re-ranks with a cross-encoder for improved precision
"""

import os
import re
import logging
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable, TYPE_CHECKING
import numpy as np

# Lazy import SentenceTransformer to avoid 10s+ PyTorch load on module import
# It will be imported on first use in SearchEngine.embedder property
if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from .models import StoryDocument
from .faiss_index import FAISSIndexManager
from .fts_index import FTS5Index

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[str, float]]],
    weights: Optional[List[float]] = None,
    k: int = 60
) -> List[Tuple[str, float]]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.
    
    RRF Formula: score(d) = Σ (weight_i / (k + rank_i(d)))
    
    This is the same algorithm Haystack's DocumentJoiner uses with
    join_mode="reciprocal_rank_fusion".
    
    Args:
        ranked_lists: List of ranked result lists, each containing (doc_id, score) tuples
        weights: Optional weights for each list (default: equal weights)
        k: RRF constant (default 60, same as Haystack)
    
    Returns:
        Combined ranked list of (doc_id, rrf_score) tuples
    """
    if not ranked_lists:
        return []
    
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    
    if len(weights) != len(ranked_lists):
        raise ValueError(f"Number of weights ({len(weights)}) must match number of lists ({len(ranked_lists)})")
    
    # Calculate RRF scores
    scores: Dict[str, float] = defaultdict(float)
    
    for weight, ranked_list in zip(weights, ranked_lists):
        for rank, (doc_id, _original_score) in enumerate(ranked_list, start=1):
            scores[doc_id] += weight / (k + rank)
    
    # Sort by RRF score descending
    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_results


class SearchEngine:
    """
    Unified search engine with hybrid semantic + keyword search.
    
    Combines:
    - FAISS index for vector similarity (semantic) search
    - SQLite FTS5 for BM25 (keyword) search  
    - Reciprocal Rank Fusion for combining results
    - Optional cross-encoder re-ranking
    
    Attributes:
        faiss_index: FAISSIndexManager for semantic search
        fts_index: FTS5Index for keyword search
        embedder: SentenceTransformer model for encoding queries
        reranker: Optional CrossEncoder for re-ranking (loaded lazily)
    """
    
    def __init__(
        self,
        data_dir: str,
        model_path: str = "BAAI/bge-large-en-v1.5",
        faiss_index_name: str = "stories.faiss",
        fts_db_name: str = "stories_fts.db",
        enable_reranker: bool = False,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ):
        """
        Initialize the search engine.
        
        Args:
            data_dir: Directory containing index files
            model_path: Path to SentenceTransformer model (local or HuggingFace)
            faiss_index_name: Filename for FAISS index
            fts_db_name: Filename for FTS5 SQLite database
            enable_reranker: Whether to use cross-encoder reranking
            reranker_model: Cross-encoder model to use for reranking
        """
        self.data_dir = Path(data_dir)
        self.model_path = model_path
        self.enable_reranker = enable_reranker
        self.reranker_model = reranker_model
        
        # Paths
        self.faiss_path = self.data_dir / faiss_index_name
        self.fts_path = self.data_dir / fts_db_name
        
        # Initialize indices
        self.faiss_index = FAISSIndexManager(dimension=1024)  # bge-large = 1024
        self.fts_index = FTS5Index(str(self.fts_path))
        
        # Lazy-loaded components
        self._embedder: Optional[SentenceTransformer] = None
        self._reranker = None
        
        # Load existing indices if available
        self._load_indices()
        
        logger.info(f"SearchEngine initialized: {self.document_count} documents")
    
    def _load_indices(self) -> None:
        """Load existing FAISS and FTS indices from disk."""
        # Load FAISS index
        if self.faiss_path.exists():
            try:
                self.faiss_index.load(str(self.faiss_path))
                logger.info(f"Loaded FAISS index: {self.faiss_index.count} vectors")
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")
        else:
            logger.info("No existing FAISS index found, will create on first add")
        
        # FTS5 index is auto-created by FTS5Index.__init__
        fts_count = self.fts_index.get_document_count()
        logger.info(f"FTS5 index: {fts_count} documents")
    
    @property
    def embedder(self) -> "SentenceTransformer":
        """Lazy-load the embedding model (defers ~10s PyTorch import)."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_path}")
            self._embedder = SentenceTransformer(self.model_path)
            logger.info("Embedding model loaded")
        return self._embedder
    
    @property
    def reranker(self):
        """Lazy-load the reranker model."""
        if self._reranker is None and self.enable_reranker:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading reranker model: {self.reranker_model}")
                self._reranker = CrossEncoder(self.reranker_model)
                logger.info("Reranker model loaded")
            except ImportError:
                logger.warning("CrossEncoder not available, disabling reranking")
                self.enable_reranker = False
        return self._reranker
    
    @property
    def document_count(self) -> int:
        """Total number of documents indexed."""
        return self.faiss_index.count
    
    def warm_up(self) -> None:
        """Pre-load models to avoid cold start latency."""
        # Force embedder to load
        _ = self.embedder
        # Optionally pre-load reranker
        if self.enable_reranker:
            _ = self.reranker
        logger.info("Search engine warmed up")
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a query string.
        
        Args:
            query: Query text
        
        Returns:
            Normalized embedding vector (1024 dims)
        """
        embedding = self.embedder.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return np.array(embedding, dtype=np.float32)
    
    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """
        Embed multiple documents.
        
        Args:
            texts: List of document texts
        
        Returns:
            Array of shape (n_docs, 1024)
        """
        embeddings = self.embedder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 10
        )
        return np.array(embeddings, dtype=np.float32)
    
    def add_document(self, doc: StoryDocument) -> None:
        """
        Add a single document to both indices.
        
        Args:
            doc: StoryDocument with content, meta, and optionally embedding
        """
        # Generate embedding if not provided
        if doc.embedding is None:
            doc.embedding = self.embed_query(doc.content)
        
        # Add to FAISS
        self.faiss_index.add_documents(
            doc_ids=[doc.id],
            embeddings=doc.embedding.reshape(1, -1),
            metadata_list=[doc.meta]
        )
        
        # Add to FTS5
        self.fts_index.add_document(
            doc_id=doc.id,
            title=doc.meta.get("title", ""),
            content=doc.content,
            book_slug=doc.meta.get("book", ""),
            pages=doc.meta.get("pages", ""),
            keywords=doc.meta.get("keywords", ""),
            start_char=doc.meta.get("start_char", 0),
            end_char=doc.meta.get("end_char", 0),
            extra_metadata={k: v for k, v in doc.meta.items() 
                          if k not in ("title", "book", "pages", "keywords", "start_char", "end_char")}
        )
    
    def add_documents(self, docs: List[StoryDocument]) -> int:
        """
        Add multiple documents to both indices.
        
        Args:
            docs: List of StoryDocument objects
        
        Returns:
            Number of documents added
        """
        if not docs:
            return 0
        
        # Separate docs with/without embeddings
        docs_needing_embedding = []
        doc_indices = []
        
        for i, doc in enumerate(docs):
            if doc.embedding is None:
                docs_needing_embedding.append(doc.content)
                doc_indices.append(i)
        
        # Batch embed documents that need it
        if docs_needing_embedding:
            logger.info(f"Embedding {len(docs_needing_embedding)} documents...")
            embeddings = self.embed_documents(docs_needing_embedding)
            for idx, embedding in zip(doc_indices, embeddings):
                docs[idx].embedding = embedding
        
        # Add to FAISS
        all_ids = [doc.id for doc in docs]
        all_embeddings = np.vstack([doc.embedding for doc in docs])
        all_metadata = [doc.meta for doc in docs]
        
        self.faiss_index.add_documents(all_ids, all_embeddings, all_metadata)
        
        # Add to FTS5
        fts_docs = []
        for doc in docs:
            fts_docs.append({
                'doc_id': doc.id,
                'title': doc.meta.get("title", ""),
                'content': doc.content,
                'book_slug': doc.meta.get("book", ""),
                'pages': doc.meta.get("pages", ""),
                'keywords': doc.meta.get("keywords", ""),
                'start_char': doc.meta.get("start_char", 0),
                'end_char': doc.meta.get("end_char", 0),
            })
        
        self.fts_index.add_documents_batch(fts_docs)
        
        logger.info(f"Added {len(docs)} documents to search indices")
        return len(docs)
    
    def search(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 100,
        min_score: float = 0.1,
        book_filter: Optional[str] = None,
        rerank: bool = False,
        rerank_top_k: int = 20,
        rrf_weights: Tuple[float, float] = (0.5, 0.5)
    ) -> List[Dict[str, Any]]:
        """
        Search for documents.
        
        Args:
            query: Search query text
            mode: Search mode - "hybrid", "semantic", "keyword", or "exact"
            top_k: Maximum number of results
            min_score: Minimum relevance score threshold
            book_filter: Optional book_slug to filter by
            rerank: Whether to apply cross-encoder reranking
            rerank_top_k: Number of candidates for reranking (before final top_k)
            rrf_weights: Weights for (semantic, keyword) in hybrid mode
        
        Returns:
            List of result dicts with title, book_slug, score, etc.
        """
        logger.info(f"Search: query='{query[:50]}...' mode={mode} top_k={top_k}")
        
        if mode == "exact":
            return self._exact_search(query, top_k, min_score, book_filter)
        
        # Build filter function for FAISS
        filter_fn = None
        if book_filter and book_filter != "All Sources":
            filter_fn = lambda doc_id, meta: meta.get("book") == book_filter
        
        # Get candidates based on mode
        if mode == "semantic":
            semantic_results = self._semantic_search(query, top_k, filter_fn)
            ranked_results = [(doc_id, score) for doc_id, score in semantic_results]
            
        elif mode == "keyword":
            keyword_results = self.fts_index.search(query, top_k, book_filter)
            ranked_results = [(doc_id, score) for doc_id, score, _ in keyword_results]
            
        elif mode == "hybrid":
            # Get results from both
            semantic_top_k = top_k * 2  # Get more candidates for fusion
            semantic_results = self._semantic_search(query, semantic_top_k, filter_fn)
            keyword_results = self.fts_index.search(query, semantic_top_k, book_filter)
            
            # Convert to ranked lists
            semantic_ranked = [(doc_id, score) for doc_id, score in semantic_results]
            keyword_ranked = [(doc_id, score) for doc_id, score, _ in keyword_results]
            
            # Apply RRF
            ranked_results = reciprocal_rank_fusion(
                [semantic_ranked, keyword_ranked],
                weights=list(rrf_weights)
            )
        else:
            raise ValueError(f"Invalid search mode: {mode}")
        
        # Optional reranking
        if rerank and self.reranker and ranked_results:
            ranked_results = self._rerank(query, ranked_results[:rerank_top_k])
            # When reranking, don't apply min_score filter - cross-encoder scores
            # are different (can be negative) and the ranking itself is the filter
            min_score = float('-inf')
        
        # Convert to result dictionaries
        results = []
        for doc_id, score in ranked_results[:top_k]:
            if score < min_score:
                continue
            
            # Get metadata
            meta = self.faiss_index.get_metadata(doc_id)
            if meta is None:
                meta = self.fts_index.get_metadata(doc_id)
            if meta is None:
                logger.warning(f"No metadata found for doc_id={doc_id}")
                continue
            
            result = {
                "title": meta.get("title", ""),
                "book_slug": meta.get("book", meta.get("book_slug", "")),
                "pages": meta.get("pages", ""),
                "keywords": meta.get("keywords", ""),
                "start_char": meta.get("start_char", 0),
                "end_char": meta.get("end_char", 0),
                "score": float(score),  # Convert numpy.float32 to native float for JSON serialization
            }
            results.append(result)
        
        logger.info(f"Search returned {len(results)} results")
        return results
    
    def _semantic_search(
        self,
        query: str,
        top_k: int,
        filter_fn: Optional[Callable] = None
    ) -> List[Tuple[str, float]]:
        """Perform semantic search using FAISS."""
        query_embedding = self.embed_query(query)
        return self.faiss_index.search(query_embedding, top_k, filter_fn)
    
    def _exact_search(
        self,
        query: str,
        top_k: int,
        min_score: float,
        book_filter: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Exact text match search (ALL words must appear).
        
        Formerly a strict phrase search, this now enforces that ALL query terms
        must be present in the document (AND logic), but order doesn't matter.
        This makes "Exact" mode more useful for finding specific combinations.
        
        Args:
            query: Search query text
            top_k: Maximum results to return
            min_score: Minimum occurrence count
            book_filter: Optional book_slug to filter by
        
        Returns:
            List of result dicts sorted by total term matches
        """
        query_text = query.strip()
        if not query_text:
            return []
        
        # Split into distinct words for "AND" matching
        # Filter out empty strings
        terms = [t for t in query_text.split() if t.strip()]
        if not terms:
            return []
            
        # Compile regex for each term for case-insensitive matching
        term_patterns = [re.compile(re.escape(term), re.IGNORECASE) for term in terms]
        
        # Get all documents (optionally filtered by book)
        all_docs = self.fts_index.get_all_documents(book_filter)
        logger.info(f"Exact search: scanning {len(all_docs)} documents for terms: {terms}")
        
        results = []
        for doc_id, content, meta in all_docs:
            term_matches = 0
            has_all_terms = True
            
            # Check for each term
            for pattern in term_patterns:
                matches = len(pattern.findall(content))
                if matches == 0:
                    has_all_terms = False
                    break
                term_matches += matches
            
            # Keep document only if ALL terms are present
            if has_all_terms:
                results.append({
                    "title": meta.get("title", ""),
                    "book_slug": meta.get("book_slug", ""),
                    "pages": meta.get("pages", ""),
                    "keywords": meta.get("keywords", ""),
                    "start_char": meta.get("start_char", 0),
                    "end_char": meta.get("end_char", 0),
                    "score": float(term_matches),  # Score = total occurrences of all terms
                    "search_query": query,
                })
        
        # Sort by score (total matches) descending and limit to top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def _rerank(
        self,
        query: str,
        ranked_results: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        """
        Re-rank results using cross-encoder.
        
        Uses full document content from FTS5 for better relevance scoring.
        
        Args:
            query: Original query
            ranked_results: List of (doc_id, score) from initial retrieval
        
        Returns:
            Re-ranked list of (doc_id, score)
        """
        if not self.reranker or not ranked_results:
            return ranked_results
        
        # Get doc_ids for batch content retrieval
        doc_ids = [doc_id for doc_id, _ in ranked_results]
        
        # Batch fetch content from FTS5 (more efficient than individual queries)
        contents = self.fts_index.get_contents_batch(doc_ids)
        
        # Build query-document pairs for cross-encoder
        pairs = []
        valid_doc_ids = []
        
        for doc_id in doc_ids:
            content = contents.get(doc_id)
            if content:
                # Use full content for best reranking quality
                # Truncate very long content to avoid memory issues
                text = content[:2000] if len(content) > 2000 else content
                pairs.append((query, text))
                valid_doc_ids.append(doc_id)
            else:
                # Fallback to metadata if content not available
                meta = self.faiss_index.get_metadata(doc_id) or self.fts_index.get_metadata(doc_id)
                if meta:
                    text = f"{meta.get('title', '')} {meta.get('keywords', '')}"
                    pairs.append((query, text))
                    valid_doc_ids.append(doc_id)
        
        if not pairs:
            return ranked_results
        
        logger.debug(f"Reranking {len(pairs)} documents with cross-encoder")
        
        # Score with cross-encoder
        scores = self.reranker.predict(pairs, show_progress_bar=False)
        
        # Re-sort by cross-encoder scores
        reranked = list(zip(valid_doc_ids, scores))
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        logger.debug(f"Reranking complete, top score: {reranked[0][1]:.4f}")
        
        return reranked
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from both indices."""
        faiss_removed = self.faiss_index.remove_documents([doc_id]) > 0
        fts_removed = self.fts_index.delete_document(doc_id)
        return faiss_removed or fts_removed
    
    def delete_by_title(self, title: str) -> int:
        """
        Delete all documents with a given title from both indices.
        
        More reliable than delete_document when doc_ids might differ between indices.
        
        Args:
            title: Story title to delete
        
        Returns:
            Total number of documents deleted
        """
        deleted_count = 0
        
        # Delete from FAISS by finding all doc_ids with this title
        doc_ids_to_remove = []
        for doc_id in list(self.faiss_index.id_map):
            meta = self.faiss_index.get_metadata(doc_id)
            if meta and meta.get("title") == title:
                doc_ids_to_remove.append(doc_id)
        
        if doc_ids_to_remove:
            deleted_count += self.faiss_index.remove_documents(doc_ids_to_remove)
            logger.info(f"Removed {len(doc_ids_to_remove)} FAISS entries for '{title}'")
        
        # Delete from FTS by title (independent of FAISS doc_ids)
        fts_deleted = self.fts_index.delete_by_title(title)
        if fts_deleted:
            deleted_count += fts_deleted
            logger.info(f"Removed {fts_deleted} FTS entries for '{title}'")
        
        return deleted_count
    
    def save(self) -> None:
        """Save indices to disk."""
        self.faiss_index.save(str(self.faiss_path))
        # FTS5 auto-saves to disk (it's SQLite)
        logger.info("Search indices saved")
    
    def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a document."""
        meta = self.faiss_index.get_metadata(doc_id)
        if meta is None:
            meta = self.fts_index.get_metadata(doc_id)
        return meta
    
    def cleanup_orphaned_entries(self, valid_titles: set) -> Tuple[int, List[str]]:
        """
        Remove entries from search indices that are not in the valid_titles set.
        
        This ensures the search index stays in sync with story_positions.json.
        Should be called on startup after loading story_positions from disk.
        
        Args:
            valid_titles: Set of story titles that should exist in the index
        
        Returns:
            Tuple of (deleted_count, list of deleted titles)
        """
        orphaned_titles = set()
        
        # Find orphaned titles in FAISS index
        for doc_id in list(self.faiss_index.id_map):
            meta = self.faiss_index.get_metadata(doc_id)
            if meta:
                title = meta.get("title")
                if title and title not in valid_titles:
                    orphaned_titles.add(title)
        
        # Find orphaned titles in FTS index
        fts_titles = self.fts_index.get_all_titles()
        for title in fts_titles:
            if title and title not in valid_titles:
                orphaned_titles.add(title)
        
        if not orphaned_titles:
            logger.info("No orphaned entries found in search indices")
            return 0, []
        
        logger.info(f"Found {len(orphaned_titles)} orphaned titles in search indices")
        
        # Delete orphaned entries
        deleted_count = 0
        deleted_titles = []
        
        for title in orphaned_titles:
            count = self.delete_by_title(title)
            deleted_count += count
            deleted_titles.append(title)
            logger.info(f"Removed orphaned story from search index: '{title}' ({count} entries)")
        
        # Save updated indices
        if deleted_count > 0:
            self.save()
        
        return deleted_count, deleted_titles


# Global search engine instance (initialized by init_search_engine)
_search_engine: Optional[SearchEngine] = None


def get_search_engine() -> SearchEngine:
    """Get the global search engine instance."""
    if _search_engine is None:
        raise RuntimeError("Search engine not initialized. Call init_search_engine() first.")
    return _search_engine


def init_search_engine(
    data_dir: str,
    model_path: str = "BAAI/bge-large-en-v1.5",
    enable_reranker: bool = False,
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
) -> SearchEngine:
    """
    Initialize the global search engine.
    
    Args:
        data_dir: Directory containing/for index files
        model_path: Path to embedding model
        enable_reranker: Whether to enable cross-encoder reranking
        reranker_model: Cross-encoder model to use for reranking
    
    Returns:
        The initialized SearchEngine instance
    """
    global _search_engine
    _search_engine = SearchEngine(
        data_dir=data_dir,
        model_path=model_path,
        enable_reranker=enable_reranker,
        reranker_model=reranker_model
    )
    return _search_engine
