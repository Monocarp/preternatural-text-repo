# backend/search/faiss_index.py
"""
FAISS index management for vector similarity search.

Provides a FAISSIndexManager class that handles:
- Loading/saving FAISS indices
- ID mapping (FAISS uses integer indices, we need string IDs)
- Similarity search with filtering
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

try:
    import faiss
except ImportError:
    faiss = None
    
logger = logging.getLogger(__name__)


class FAISSIndexManager:
    """
    Manages a FAISS index with ID mapping for story search.
    
    FAISS indices use integer positions, so we maintain a separate
    mapping from position -> story_id for retrieval.
    
    Attributes:
        index: The FAISS index (IndexFlatIP for inner product / cosine similarity)
        id_map: List of story IDs in the same order as FAISS vectors
        dimension: Embedding dimension (1024 for bge-large-en-v1.5)
    """
    
    def __init__(self, dimension: int = 1024):
        """
        Initialize a new FAISS index manager.
        
        Args:
            dimension: Embedding vector dimension (default 1024 for bge-large)
        """
        if faiss is None:
            raise ImportError("faiss-cpu is required. Install with: pip install faiss-cpu")
        
        self.dimension = dimension
        self.index: Optional[faiss.Index] = None
        self.id_map: List[str] = []  # Position -> document ID
        self.metadata: Dict[str, Dict[str, Any]] = {}  # doc_id -> metadata
        
        logger.debug(f"FAISSIndexManager initialized with dimension={dimension}")
    
    def create_index(self, use_gpu: bool = False) -> None:
        """
        Create a new empty FAISS index.
        
        Uses IndexFlatIP (inner product) which is equivalent to cosine similarity
        when vectors are normalized (which bge-large embeddings are).
        
        Args:
            use_gpu: Whether to use GPU acceleration (requires faiss-gpu)
        """
        # IndexFlatIP: exact inner product search (cosine sim for normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.id_map = []
        self.metadata = {}
        logger.info(f"Created new FAISS IndexFlatIP with dimension {self.dimension}")
    
    def add_documents(self, doc_ids: List[str], embeddings: np.ndarray, 
                     metadata_list: Optional[List[Dict]] = None) -> int:
        """
        Add documents to the index.
        
        Args:
            doc_ids: List of document IDs
            embeddings: numpy array of shape (n_docs, dimension)
            metadata_list: Optional list of metadata dicts for each document
        
        Returns:
            Number of documents added
        """
        if self.index is None:
            self.create_index()
        
        # Ensure embeddings are contiguous float32
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
        
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        if embeddings.shape[1] != self.dimension:
            raise ValueError(f"Embedding dimension {embeddings.shape[1]} != index dimension {self.dimension}")
        
        if len(doc_ids) != embeddings.shape[0]:
            raise ValueError(f"Number of IDs ({len(doc_ids)}) != number of embeddings ({embeddings.shape[0]})")
        
        # Add to FAISS index
        self.index.add(embeddings)
        
        # Update ID map
        for i, doc_id in enumerate(doc_ids):
            self.id_map.append(doc_id)
            if metadata_list and i < len(metadata_list):
                self.metadata[doc_id] = metadata_list[i]
        
        logger.debug(f"Added {len(doc_ids)} documents to FAISS index (total: {self.index.ntotal})")
        return len(doc_ids)
    
    def search(self, query_embedding: np.ndarray, top_k: int = 100,
               filter_fn: Optional[callable] = None) -> List[Tuple[str, float]]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector of shape (dimension,) or (1, dimension)
            top_k: Number of results to return
            filter_fn: Optional function(doc_id, metadata) -> bool for filtering
        
        Returns:
            List of (doc_id, score) tuples, sorted by descending score
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search called on empty FAISS index")
            return []
        
        # Ensure query is correct shape
        query_embedding = np.ascontiguousarray(query_embedding, dtype=np.float32)
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # If filtering, we need to retrieve more candidates
        search_k = top_k * 3 if filter_fn else top_k
        search_k = min(search_k, self.index.ntotal)
        
        # Search FAISS
        scores, indices = self.index.search(query_embedding, search_k)
        
        # Convert to (doc_id, score) pairs
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.id_map):
                continue
            
            doc_id = self.id_map[idx]
            
            # Apply filter if provided
            if filter_fn:
                meta = self.metadata.get(doc_id, {})
                if not filter_fn(doc_id, meta):
                    continue
            
            results.append((doc_id, float(score)))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def remove_documents(self, doc_ids: List[str]) -> int:
        """
        Remove documents from the index by rebuilding without them.
        
        Note: FAISS doesn't support efficient deletion, so this rebuilds the index.
        For frequent deletions, consider using IndexIDMap or IndexIVF.
        
        Args:
            doc_ids: List of document IDs to remove
        
        Returns:
            Number of documents removed
        """
        if self.index is None:
            return 0
        
        doc_ids_set = set(doc_ids)
        
        # Collect vectors and IDs to keep
        keep_vectors = []
        keep_ids = []
        keep_metadata = []
        removed_count = 0
        
        for idx, doc_id in enumerate(self.id_map):
            if doc_id in doc_ids_set:
                removed_count += 1
                if doc_id in self.metadata:
                    del self.metadata[doc_id]
            else:
                # Reconstruct vector from index
                vector = np.zeros((1, self.dimension), dtype=np.float32)
                self.index.reconstruct(idx, vector[0])
                keep_vectors.append(vector)
                keep_ids.append(doc_id)
                keep_metadata.append(self.metadata.get(doc_id, {}))
        
        # Rebuild index
        self.create_index()
        if keep_vectors:
            embeddings = np.vstack(keep_vectors)
            self.add_documents(keep_ids, embeddings, keep_metadata)
        
        logger.info(f"Removed {removed_count} documents from FAISS index")
        return removed_count
    
    def save(self, index_path: str, mapping_path: Optional[str] = None) -> None:
        """
        Save the FAISS index and ID mapping to disk.
        
        Args:
            index_path: Path for the .faiss or .bin index file
            mapping_path: Path for the ID mapping JSON (defaults to index_path + '.map.json')
        """
        if self.index is None:
            raise ValueError("No index to save")
        
        if mapping_path is None:
            mapping_path = str(index_path) + '.map.json'
        
        # Save FAISS index
        faiss.write_index(self.index, str(index_path))
        
        # Save ID mapping and metadata
        mapping_data = {
            "id_map": self.id_map,
            "metadata": self.metadata,
            "dimension": self.dimension
        }
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, sort_keys=True)
        
        logger.info(f"Saved FAISS index ({self.index.ntotal} vectors) to {index_path}")
    
    def load(self, index_path: str, mapping_path: Optional[str] = None) -> int:
        """
        Load the FAISS index and ID mapping from disk.
        
        Args:
            index_path: Path to the .faiss or .bin index file
            mapping_path: Path to the ID mapping JSON (defaults to index_path + '.map.json')
        
        Returns:
            Number of documents loaded
        """
        if mapping_path is None:
            mapping_path = str(index_path) + '.map.json'
        
        # Load FAISS index
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
        
        self.index = faiss.read_index(str(index_path))
        
        # Load ID mapping
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            self.id_map = mapping_data.get("id_map", [])
            self.metadata = mapping_data.get("metadata", {})
            self.dimension = mapping_data.get("dimension", self.dimension)
        else:
            # Index exists but no mapping - create empty mapping
            logger.warning(f"ID mapping not found at {mapping_path}, creating empty mapping")
            self.id_map = [str(i) for i in range(self.index.ntotal)]
            self.metadata = {}
        
        logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors from {index_path}")
        return self.index.ntotal
    
    @property
    def count(self) -> int:
        """Number of documents in the index."""
        return self.index.ntotal if self.index else 0
    
    def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a document by ID."""
        return self.metadata.get(doc_id)
    
    def update_metadata(self, doc_id: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata for a document."""
        if doc_id not in self.metadata and doc_id not in self.id_map:
            return False
        self.metadata[doc_id] = metadata
        return True
