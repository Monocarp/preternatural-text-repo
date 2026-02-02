# backend/search/fts_index.py
"""
SQLite FTS5 full-text search index for keyword/BM25 search.

Replaces Haystack's InMemoryBM25Retriever with a persistent, fast SQLite FTS5 index.
FTS5 provides:
- BM25 ranking (same algorithm as Haystack BM25)
- Persistence (no reload on restart)
- Better tokenization and stemming options
- Efficient incremental updates
"""

import os
import re
import sqlite3
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FTS5Index:
    """
    SQLite FTS5 full-text search index for story content.
    
    Provides BM25-ranked keyword search with:
    - Persistent storage (survives restarts)
    - Fast incremental updates
    - Metadata filtering via JOIN
    
    Schema:
        stories_fts: FTS5 virtual table (doc_id, title, content)
        stories_meta: Regular table (doc_id PRIMARY KEY, metadata JSON)
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the FTS5 index.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_tables()
        logger.debug(f"FTS5Index initialized at {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _ensure_tables(self) -> None:
        """Create FTS5 and metadata tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # FTS5 virtual table for full-text search
            # tokenize='porter unicode61' provides stemming + unicode support
            # Added keywords to FTS table for rich metadata search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS stories_fts USING fts5(
                    doc_id,
                    title,
                    content,
                    keywords,
                    tokenize='porter unicode61'
                )
            """)
            
            # Metadata table (for filtering and additional data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stories_meta (
                    doc_id TEXT PRIMARY KEY,
                    book_slug TEXT,
                    pages TEXT,
                    keywords TEXT,
                    start_char INTEGER,
                    end_char INTEGER,
                    metadata_json TEXT
                )
            """)
            
            # Index on book_slug for filtering
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stories_meta_book 
                ON stories_meta(book_slug)
            """)
            
            conn.commit()
            logger.debug("FTS5 tables ensured")
    
    def add_document(self, doc_id: str, title: str, content: str,
                    book_slug: str = "", pages: str = "", keywords: str = "",
                    start_char: int = 0, end_char: int = 0,
                    extra_metadata: Optional[Dict] = None) -> None:
        """
        Add a document to the FTS5 index.
        
        Args:
            doc_id: Unique document identifier
            title: Story title
            content: Full story text
            book_slug: Book identifier for filtering
            pages: Page numbers
            keywords: Comma-separated keywords
            start_char: Start position in full text
            end_char: End position in full text
            extra_metadata: Additional metadata as JSON
        """
        import json
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert or replace in FTS table
            cursor.execute("""
                INSERT OR REPLACE INTO stories_fts(doc_id, title, content, keywords)
                VALUES (?, ?, ?, ?)
            """, (doc_id, title, content, keywords))
            
            # Insert or replace in metadata table
            metadata_json = json.dumps(extra_metadata) if extra_metadata else None
            cursor.execute("""
                INSERT OR REPLACE INTO stories_meta(
                    doc_id, book_slug, pages, keywords, start_char, end_char, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, book_slug, pages, keywords, start_char, end_char, metadata_json))
            
            conn.commit()
    
    def add_documents_batch(self, documents: List[Dict[str, Any]]) -> int:
        """
        Add multiple documents in a single transaction.
        
        Args:
            documents: List of dicts with keys: doc_id, title, content, book_slug, etc.
        
        Returns:
            Number of documents added
        """
        import json
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for doc in documents:
                # Include keywords in FTS insert
                cursor.execute("""
                    INSERT OR REPLACE INTO stories_fts(doc_id, title, content, keywords)
                    VALUES (?, ?, ?, ?)
                """, (
                    doc['doc_id'], 
                    doc.get('title', ''), 
                    doc.get('content', ''),
                    doc.get('keywords', '')
                ))
                
                extra_meta = doc.get('extra_metadata')
                metadata_json = json.dumps(extra_meta) if extra_meta else None
                
                cursor.execute("""
                    INSERT OR REPLACE INTO stories_meta(
                        doc_id, book_slug, pages, keywords, start_char, end_char, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc['doc_id'],
                    doc.get('book_slug', ''),
                    doc.get('pages', ''),
                    doc.get('keywords', ''),
                    doc.get('start_char', 0),
                    doc.get('end_char', 0),
                    metadata_json
                ))
            
            conn.commit()
            logger.info(f"Added {len(documents)} documents to FTS5 index")
            return len(documents)
    
    def search(self, query: str, top_k: int = 100,
               book_filter: Optional[str] = None) -> List[Tuple[str, float, Dict]]:
        """
        Search for documents using BM25 ranking.
        
        Args:
            query: Search query text
            top_k: Maximum number of results
            book_filter: Optional book_slug to filter by
        
        Returns:
            List of (doc_id, bm25_score, metadata_dict) tuples
        """
        # Escape special FTS5 characters and prepare query
        # FTS5 treats these as operators: AND OR NOT * ^ " 
        safe_query = self._prepare_query(query)
        
        if not safe_query.strip():
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # BM25 scoring with metadata join
            # bm25(stories_fts, w_docid, w_title, w_content, w_keywords)
            # Weights: Title (2.0), Content (1.0), Keywords (1.5)
            # Note: doc_id weight is usually ignored or 0
            if book_filter:
                cursor.execute("""
                    SELECT 
                        f.doc_id,
                        bm25(stories_fts, 0.0, 2.0, 1.0, 1.5) as score,
                        m.book_slug,
                        m.pages,
                        m.keywords,
                        m.start_char,
                        m.end_char,
                        m.metadata_json,
                        f.title
                    FROM stories_fts f
                    JOIN stories_meta m ON f.doc_id = m.doc_id
                    WHERE stories_fts MATCH ?
                    AND m.book_slug = ?
                    ORDER BY score
                    LIMIT ?
                """, (safe_query, book_filter, top_k))
            else:
                cursor.execute("""
                    SELECT 
                        f.doc_id,
                        bm25(stories_fts, 0.0, 2.0, 1.0, 1.5) as score,
                        m.book_slug,
                        m.pages,
                        m.keywords,
                        m.start_char,
                        m.end_char,
                        m.metadata_json,
                        f.title
                    FROM stories_fts f
                    JOIN stories_meta m ON f.doc_id = m.doc_id
                    WHERE stories_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                """, (safe_query, top_k))
            
            results = []
            for row in cursor.fetchall():
                import json
                
                # BM25 returns negative scores (more negative = better match)
                # Negate to get positive scores where higher = better
                bm25_score = -row['score']
                
                metadata = {
                    'title': row['title'],
                    'book_slug': row['book_slug'],
                    'pages': row['pages'],
                    'keywords': row['keywords'],
                    'start_char': row['start_char'],
                    'end_char': row['end_char'],
                }
                
                if row['metadata_json']:
                    try:
                        extra = json.loads(row['metadata_json'])
                        metadata.update(extra)
                    except json.JSONDecodeError:
                        pass
                
                results.append((row['doc_id'], bm25_score, metadata))
            
            return results
    
    def _prepare_query(self, query: str) -> str:
        """
        Prepare a query string for FTS5 MATCH.
        
        Handles:
        - Multi-word queries (implicit AND)
        - Special character escaping
        - Phrase queries (quoted strings preserved)
        """
        # If query contains quotes, preserve phrase search
        if '"' in query:
            return query
        
        # Split into words and filter out FTS operators
        words = query.strip().split()
        filtered = []
        skip_next = False
        
        for word in words:
            upper = word.upper()
            if upper in ('AND', 'OR', 'NOT'):
                # Skip standalone operators
                continue
            if upper == 'NEAR':
                skip_next = True
                continue
            if skip_next:
                skip_next = False
                continue
            
            # Escape special characters within words
            # Keep alphanumeric and basic punctuation
            clean = re.sub(r'[^\w\s\'-]', '', word)
            if clean:
                filtered.append(clean)
        
        # Join with spaces (FTS5 default is AND)
        return ' '.join(filtered)
    
    def update_keywords(self, title: str, keywords: str) -> int:
        """
        Update keywords for all documents with the given title.
        
        Args:
            title: Story title to update
            keywords: New keywords string
        
        Returns:
            Number of documents updated
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # First get doc_ids for this title
            cursor.execute("SELECT doc_id FROM stories_fts WHERE title = ?", (title,))
            doc_ids = [row['doc_id'] for row in cursor.fetchall()]
            
            if not doc_ids:
                logger.debug(f"No documents found for title '{title}' in FTS5")
                return 0
            
            # Update keywords in metadata table
            for doc_id in doc_ids:
                cursor.execute(
                    "UPDATE stories_meta SET keywords = ? WHERE doc_id = ?",
                    (keywords, doc_id)
                )
            
            conn.commit()
            logger.debug(f"Updated keywords for {len(doc_ids)} documents with title '{title}'")
            return len(doc_ids)
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the index.
        
        Args:
            doc_id: Document ID to delete
        
        Returns:
            True if document was found and deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM stories_fts WHERE doc_id = ?", (doc_id,))
            cursor.execute("DELETE FROM stories_meta WHERE doc_id = ?", (doc_id,))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                logger.debug(f"Deleted document {doc_id} from FTS5 index")
            
            return deleted
    
    def delete_by_title(self, title: str) -> int:
        """
        Delete all documents matching a title.
        
        Args:
            title: Story title to delete
        
        Returns:
            Number of documents deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # First, get doc_ids matching this title from FTS table
            cursor.execute("SELECT doc_id FROM stories_fts WHERE title = ?", (title,))
            doc_ids = [row['doc_id'] for row in cursor.fetchall()]
            
            if not doc_ids:
                return 0
            
            # Delete from both tables
            placeholders = ','.join('?' * len(doc_ids))
            cursor.execute(f"DELETE FROM stories_fts WHERE doc_id IN ({placeholders})", doc_ids)
            cursor.execute(f"DELETE FROM stories_meta WHERE doc_id IN ({placeholders})", doc_ids)
            
            conn.commit()
            logger.info(f"Deleted {len(doc_ids)} documents with title '{title}' from FTS5 index")
            return len(doc_ids)
    
    def delete_by_book(self, book_slug: str) -> int:
        """
        Delete all documents for a book.
        
        Args:
            book_slug: Book identifier
        
        Returns:
            Number of documents deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get doc_ids to delete
            cursor.execute(
                "SELECT doc_id FROM stories_meta WHERE book_slug = ?",
                (book_slug,)
            )
            doc_ids = [row['doc_id'] for row in cursor.fetchall()]
            
            if not doc_ids:
                return 0
            
            # Delete from both tables
            placeholders = ','.join('?' * len(doc_ids))
            cursor.execute(f"DELETE FROM stories_fts WHERE doc_id IN ({placeholders})", doc_ids)
            cursor.execute(f"DELETE FROM stories_meta WHERE doc_id IN ({placeholders})", doc_ids)
            
            conn.commit()
            logger.info(f"Deleted {len(doc_ids)} documents for book {book_slug}")
            return len(doc_ids)
    
    def get_document_count(self) -> int:
        """Get total number of documents in the index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stories_meta")
            return cursor.fetchone()[0]
    
    def get_content(self, doc_id: str) -> Optional[str]:
        """
        Get the full content of a document for reranking.
        
        Args:
            doc_id: Document ID
        
        Returns:
            Document content string or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM stories_fts WHERE doc_id = ?",
                (doc_id,)
            )
            row = cursor.fetchone()
            return row['content'] if row else None
    
    def get_contents_batch(self, doc_ids: List[str]) -> Dict[str, str]:
        """
        Get content for multiple documents efficiently.
        
        Args:
            doc_ids: List of document IDs
        
        Returns:
            Dict mapping doc_id to content
        """
        if not doc_ids:
            return {}
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(doc_ids))
            cursor.execute(
                f"SELECT doc_id, content FROM stories_fts WHERE doc_id IN ({placeholders})",
                doc_ids
            )
            return {row['doc_id']: row['content'] for row in cursor.fetchall()}
    
    def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific document."""
        import json
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    f.title,
                    m.book_slug,
                    m.pages,
                    m.keywords,
                    m.start_char,
                    m.end_char,
                    m.metadata_json
                FROM stories_meta m
                JOIN stories_fts f ON m.doc_id = f.doc_id
                WHERE m.doc_id = ?
            """, (doc_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            metadata = {
                'title': row['title'],
                'book_slug': row['book_slug'],
                'pages': row['pages'],
                'keywords': row['keywords'],
                'start_char': row['start_char'],
                'end_char': row['end_char'],
            }
            
            if row['metadata_json']:
                try:
                    extra = json.loads(row['metadata_json'])
                    metadata.update(extra)
                except json.JSONDecodeError:
                    pass
            
            return metadata
    
    def clear(self) -> None:
        """Clear all documents from the index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stories_fts")
            cursor.execute("DELETE FROM stories_meta")
            conn.commit()
            logger.info("Cleared FTS5 index")
    
    def get_all_titles(self) -> List[str]:
        """
        Get all unique story titles in the FTS index.
        
        Returns:
            List of all unique titles
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT title FROM stories_fts WHERE title IS NOT NULL AND title != ''")
            return [row['title'] for row in cursor.fetchall()]
    
    def get_all_documents(self, book_filter: Optional[str] = None) -> List[Tuple[str, str, Dict]]:
        """
        Get all documents with content and metadata for exact search.
        
        Args:
            book_filter: Optional book_slug to filter by
        
        Returns:
            List of (doc_id, content, metadata) tuples
        """
        import json
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if book_filter:
                cursor.execute("""
                    SELECT 
                        f.doc_id,
                        f.content,
                        f.title,
                        m.book_slug,
                        m.pages,
                        m.keywords,
                        m.start_char,
                        m.end_char,
                        m.metadata_json
                    FROM stories_fts f
                    JOIN stories_meta m ON f.doc_id = m.doc_id
                    WHERE m.book_slug = ?
                """, (book_filter,))
            else:
                cursor.execute("""
                    SELECT 
                        f.doc_id,
                        f.content,
                        f.title,
                        m.book_slug,
                        m.pages,
                        m.keywords,
                        m.start_char,
                        m.end_char,
                        m.metadata_json
                    FROM stories_fts f
                    JOIN stories_meta m ON f.doc_id = m.doc_id
                """)
            
            results = []
            for row in cursor.fetchall():
                metadata = {
                    'title': row['title'],
                    'book_slug': row['book_slug'],
                    'pages': row['pages'],
                    'keywords': row['keywords'],
                    'start_char': row['start_char'],
                    'end_char': row['end_char'],
                }
                
                if row['metadata_json']:
                    try:
                        extra = json.loads(row['metadata_json'])
                        metadata.update(extra)
                    except json.JSONDecodeError:
                        pass
                
                results.append((row['doc_id'], row['content'], metadata))
            
            return results
    
    def vacuum(self) -> None:
        """Optimize the database (reclaim space after deletions)."""
        with self._get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("Vacuumed FTS5 database")
