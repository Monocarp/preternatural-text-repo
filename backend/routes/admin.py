# backend/routes/admin.py
"""
Admin routes for the Lexicon API.

Endpoints:
- POST /api/export - Export stories to markdown/PDF/Word
- POST /api/migrate-db - Recreate database tables (editor)
- POST /api/reload-stories - Force reload from disk (editor)
- POST /api/cleanup-search-index - Remove orphaned search entries
"""

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Depends

from .dependencies import ExportBody, require_editor
from utils import (
    export_stories, sync_disk_to_db, invalidate_cache,
    preload_book_metadata, clear_book_metadata_cache,
    get_cached_tree, stories_dict, story_positions, engine
)
from models import Base

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/export")
def export(body: ExportBody):
    """
    Export stories to markdown, PDF, or Word format.
    
    Returns base64-encoded file data with mime type and filename.
    """
    result = export_stories(body.stories, format=body.format, is_single=body.is_single)
    if not result:
        raise HTTPException(500, "Export failed")
    return result


@router.post("/migrate-db")
def migrate_database(user: Dict = Depends(require_editor)):
    """
    Recreate database tables to apply schema changes.
    
    WARNING: This will drop all existing data!
    Data is reloaded from disk files after migration.
    """
    try:
        log.info("Starting database migration...")
        
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        log.info("Dropped all existing tables")
        
        # Recreate all tables
        Base.metadata.create_all(bind=engine)
        log.info("Recreated all tables with new schema")
        
        # Reload from disk
        sync_disk_to_db()
        
        # Clear and reload caches
        clear_book_metadata_cache()
        preload_book_metadata()
        invalidate_cache()
        
        return {
            "status": "success",
            "message": "Database migrated successfully. All data reloaded from disk."
        }
        
    except Exception as e:
        log.error(f"Migration failed: {e}", exc_info=True)
        raise HTTPException(500, f"Migration failed: {str(e)}")


@router.post("/reload-stories")
def reload_stories(user: Dict = Depends(require_editor)):
    """
    Force reload of stories from disk and sync to database.
    
    Useful after running pre-processing scripts or manually
    updating story_positions.json files.
    """
    try:
        log.info("Manual reload triggered by user")
        
        sync_disk_to_db()
        clear_book_metadata_cache()
        preload_book_metadata()
        invalidate_cache()
        
        # Force immediate reload to verify
        tree = get_cached_tree()
        
        return {
            "status": "success",
            "message": "Stories reloaded from disk and synced to database",
            "story_count": len(stories_dict),
            "tree_categories": len(tree)
        }
    except Exception as e:
        log.error(f"Reload failed: {e}", exc_info=True)
        raise HTTPException(500, f"Reload failed: {str(e)}")


@router.post("/cleanup-search-index")
def cleanup_search_index():
    """
    Remove orphaned entries from search indices.
    
    Finds stories in the search index that no longer exist in
    story_positions.json and removes them. Useful for fixing
    stale search results after story deletions.
    
    No auth required - this is a safe cleanup operation.
    """
    from search import USE_DIRECT_SEARCH
    
    # Build set of valid titles
    valid_titles = set()
    for book_slug, positions in story_positions.items():
        valid_titles.update(positions.keys())
    
    log.info(f"Valid titles in story_positions: {len(valid_titles)}")
    
    orphaned_titles = set()
    deleted_count = 0
    
    try:
        if USE_DIRECT_SEARCH:
            from search.engine import get_search_engine
            search_engine = get_search_engine()
            
            # Find orphaned titles
            for doc_id in list(search_engine.faiss_index.id_map):
                meta = search_engine.faiss_index.get_metadata(doc_id)
                if meta:
                    title = meta.get("title")
                    if title and title not in valid_titles:
                        orphaned_titles.add(title)
            
            log.info(f"Found {len(orphaned_titles)} orphaned titles")
            
            # Delete orphaned entries
            for title in orphaned_titles:
                count = search_engine.delete_by_title(title)
                deleted_count += count
                log.info(f"Removed orphaned story: '{title}' ({count} entries)")
            
            if deleted_count > 0:
                search_engine.save()
        else:
            # Legacy Haystack
            from utils import document_store, document_store_path
            import numpy as np
            
            all_docs = list(document_store.filter_documents({}))
            log.info(f"Total documents in Haystack store: {len(all_docs)}")
            
            orphaned_doc_ids = []
            for doc in all_docs:
                title = doc.meta.get("title") if doc.meta else None
                if title and title not in valid_titles:
                    orphaned_titles.add(title)
                    orphaned_doc_ids.append(doc.id)
            
            if orphaned_doc_ids:
                document_store.delete_documents(orphaned_doc_ids)
                deleted_count = len(orphaned_doc_ids)
                
                remaining_docs = list(document_store.filter_documents({}))
                docs_to_update = []
                for doc in remaining_docs:
                    if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                        doc.embedding = doc.embedding.tolist()
                        docs_to_update.append(doc)
                
                if docs_to_update:
                    document_store.delete_documents([doc.id for doc in docs_to_update])
                    document_store.write_documents(docs_to_update)
                
                document_store.save_to_disk(document_store_path)
        
        # Sync to GitHub if changes were made
        if deleted_count > 0:
            try:
                from sync.github_sync import sync_document_store, sync_documents_json
                sync_document_store(f"Cleanup: removed {len(orphaned_titles)} orphaned stories")
                sync_documents_json(f"Cleanup: removed {len(orphaned_titles)} orphaned stories")
                log.info("Synced document store to GitHub")
            except Exception as e:
                log.warning(f"Failed to sync to GitHub: {e}")
        
        invalidate_cache()
        
        return {
            "status": "success",
            "message": f"Cleaned up {len(orphaned_titles)} orphaned stories ({deleted_count} index entries)",
            "orphaned_titles": list(orphaned_titles),
            "valid_story_count": len(valid_titles),
            "synced_to_github": deleted_count > 0
        }
        
    except Exception as e:
        log.error(f"Search index cleanup failed: {e}", exc_info=True)
        raise HTTPException(500, f"Cleanup failed: {str(e)}")
