# backend/search/models.py
"""
Data models for the search engine.

Replaces Haystack's Document class with a lightweight, typed dataclass.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np


@dataclass
class StoryDocument:
    """
    A story document with content, metadata, embedding, and search score.
    
    Replaces haystack.Document with a simpler, typed alternative.
    
    Attributes:
        id: Unique document identifier (typically "{book_slug}_{title_hash}")
        content: The full story text
        meta: Dictionary of metadata (title, book, pages, keywords, etc.)
        embedding: Optional numpy array of the story embedding (1024 dims for bge-large)
        score: Search relevance score (set during retrieval)
    """
    id: str
    content: str
    meta: dict = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None
    score: float = 0.0
    
    @property
    def title(self) -> str:
        """Convenience accessor for meta.title"""
        return self.meta.get("title", "")
    
    @property
    def book_slug(self) -> str:
        """Convenience accessor for meta.book"""
        return self.meta.get("book", "unknown")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "meta": self.meta,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "score": self.score
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StoryDocument":
        """Create from dictionary (e.g., from JSON)."""
        embedding = data.get("embedding")
        if embedding is not None:
            embedding = np.array(embedding, dtype=np.float32)
        
        return cls(
            id=data["id"],
            content=data["content"],
            meta=data.get("meta", {}),
            embedding=embedding,
            score=data.get("score", 0.0)
        )
    
    @classmethod
    def from_haystack_doc(cls, doc: Any) -> "StoryDocument":
        """
        Convert from a Haystack Document (for migration).
        
        Args:
            doc: A haystack.Document instance
        
        Returns:
            StoryDocument equivalent
        """
        embedding = doc.embedding
        if embedding is not None and isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        
        return cls(
            id=doc.id,
            content=doc.content or "",
            meta=dict(doc.meta) if doc.meta else {},
            embedding=embedding,
            score=getattr(doc, 'score', 0.0)
        )
