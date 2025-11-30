# backend/storage/stories.py
"""
Story update operations.

Handles updating story metadata:
- Boundary changes (start_char, end_char)
- Title changes (propagates to tree, database, document store)

Works with both legacy Haystack and Direct FAISS + SQLite search engines.
"""

import json
import logging
import numpy as np

from state import app_state
from .books import load_story_positions, save_story_positions

logger = logging.getLogger(__name__)


def _update_document_store_metadata(old_title: str, new_title: str) -> None:
    """
    Update document store metadata for a title change.
    
    Handles both legacy Haystack and Direct search engine.
    """
    from search import USE_DIRECT_SEARCH
    
    if USE_DIRECT_SEARCH:
        # Direct engine: update FAISS metadata and FTS5
        try:
            from search.engine import get_search_engine
            engine = get_search_engine()
            
            # Update FAISS metadata
            for doc_id in engine.faiss_index.id_map:
                meta = engine.faiss_index.get_metadata(doc_id)
                if meta and meta.get("title") == old_title:
                    meta["title"] = new_title
                    engine.faiss_index.update_metadata(doc_id, meta)
                    logger.info(f"Updated FAISS metadata for doc {doc_id}")
            
            # For FTS5, we need to delete and re-add (no in-place update)
            # Get the metadata first
            fts_meta = engine.fts_index.get_metadata(doc_id)
            if fts_meta:
                # We'd need the content to re-add, which we don't store
                # For now, log a warning - a full re-index may be needed
                logger.warning(
                    f"FTS5 title update may require re-indexing for '{old_title}'"
                )
            
            engine.save()
            logger.info(f"Saved search indices after title update")
            
        except Exception as e:
            logger.error(f"Failed to update Direct search indices: {e}", exc_info=True)
    else:
        # Legacy Haystack: use document_store methods
        document_store = app_state.document_store
        if document_store:
            try:
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
                    document_store.save_to_disk(app_state.document_store_path)
                    logger.info(f"Updated document store for {len(updated_docs)} documents")
                else:
                    logger.warning(f"No documents found with title '{old_title}'")
            except Exception as e:
                logger.error(f"Failed to update document store: {e}", exc_info=True)


def _update_document_store_keywords(title: str, keywords: str) -> None:
    """
    Update document store metadata for keywords change.
    
    Handles both legacy Haystack and Direct search engine.
    """
    from search import USE_DIRECT_SEARCH
    
    if USE_DIRECT_SEARCH:
        # Direct engine: update both FAISS and FTS5 metadata
        try:
            from search.engine import get_search_engine
            engine = get_search_engine()
            
            # Update FAISS metadata
            for doc_id in engine.faiss_index.id_map:
                meta = engine.faiss_index.get_metadata(doc_id)
                if meta and meta.get("title") == title:
                    meta["keywords"] = keywords
                    engine.faiss_index.update_metadata(doc_id, meta)
                    logger.info(f"Updated FAISS keywords metadata for doc {doc_id}")
            
            # Update FTS5 metadata
            updated_count = engine.fts_index.update_keywords(title, keywords)
            if updated_count > 0:
                logger.info(f"Updated FTS5 keywords for {updated_count} documents")
            
            engine.save()
            logger.info(f"Saved search indices after keywords update")
            
        except Exception as e:
            logger.error(f"Failed to update Direct search indices for keywords: {e}", exc_info=True)
    else:
        # Legacy Haystack: use document_store methods
        document_store = app_state.document_store
        if document_store:
            try:
                updated_docs = []
                for doc in document_store.filter_documents({}):
                    if doc.meta.get("title") == title:
                        doc.meta["keywords"] = keywords
                        updated_docs.append(doc)
                        logger.info(f"Found document to update keywords: {doc.id}")
                
                if updated_docs:
                    logger.info(f"Updating keywords for {len(updated_docs)} documents in document store")
                    for doc in updated_docs:
                        if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                            doc.embedding = doc.embedding.tolist()
                    
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
                    
                    document_store.save_to_disk(app_state.document_store_path)
                    logger.info(f"Updated document store keywords for {len(updated_docs)} documents")
                else:
                    logger.warning(f"No documents found with title '{title}'")
            except Exception as e:
                logger.error(f"Failed to update document store keywords: {e}", exc_info=True)


def update_story_boundaries(book_slug: str, title: str, start_char: int, end_char: int) -> bool:
    """
    Update story boundaries in both JSON and database.
    
    Args:
        book_slug: The book identifier
        title: Story title
        start_char: New start character position
        end_char: New end character position
    
    Returns:
        True if update succeeded, False otherwise
    """
    positions = load_story_positions(book_slug)
    
    if title not in positions:
        logger.warning(f"Story {title} not found in {book_slug}")
        return False
    
    # Update in-memory cache
    positions[title]["start_char"] = start_char
    positions[title]["end_char"] = end_char
    app_state.story_positions[book_slug] = positions
    
    # Update stories_dict cache
    if title in app_state.stories_dict:
        app_state.stories_dict[title]["start_char"] = start_char
        app_state.stories_dict[title]["end_char"] = end_char
    
    # Save to JSON file
    save_success = save_story_positions(book_slug)
    
    # Update database if available
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            from models import Story
            with app_state.SessionLocal() as db:
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
    from utils.cache import invalidate_cache
    invalidate_cache()
    logger.info(f"Invalidated cache after updating boundaries for {title}")
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_story_boundary_change
        on_story_boundary_change(book_slug, title)
    except Exception as e:
        logger.debug(f"GitHub sync skipped: {e}")
    
    return save_success


def update_story_keywords(book_slug: str, title: str, keywords: str) -> bool:
    """
    Update story keywords in JSON, database, and document store.
    
    Args:
        book_slug: The book identifier
        title: Story title
        keywords: New keywords string (comma-separated)
    
    Returns:
        True if update succeeded, False otherwise
    """
    from utils.cache import invalidate_cache
    
    positions = load_story_positions(book_slug)
    
    if title not in positions:
        logger.warning(f"Story '{title}' not found in {book_slug}")
        return False
    
    # Parse keywords - accept both comma-separated string and list
    if isinstance(keywords, str):
        keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
    else:
        keywords_list = list(keywords)
    
    keywords_str = ', '.join(keywords_list)
    
    # Update in-memory cache
    positions[title]["keywords"] = keywords_list
    app_state.story_positions[book_slug] = positions
    
    # Update stories_dict cache
    if title in app_state.stories_dict:
        app_state.stories_dict[title]["keywords"] = keywords_str
    
    # Save to JSON file
    save_success = save_story_positions(book_slug)
    
    # Also save stories_dict.json
    try:
        with open(app_state.stories_dict_path, "w") as f:
            json.dump(app_state.stories_dict, f, indent=4, sort_keys=True)
    except Exception as e:
        logger.error(f"Failed to save stories_dict.json: {e}")
    
    # Update database if available
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            from models import Story
            with app_state.SessionLocal() as db:
                story = db.query(Story).filter_by(title=title, book_slug=book_slug).first()
                if story:
                    story.keywords = keywords_str
                    db.commit()
                    logger.info(f"Updated keywords for story '{title}' in database")
                else:
                    logger.warning(f"Story '{title}' not found in database")
        except Exception as e:
            logger.error(f"Failed to update database keywords for '{title}': {e}")
    
    # Update document store metadata
    _update_document_store_keywords(title, keywords_str)
    
    # Invalidate cache since data changed
    invalidate_cache()
    logger.info(f"Updated keywords for story '{title}' to: {keywords_str}")
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_story_keywords_change
        on_story_keywords_change(book_slug, title)
    except Exception as e:
        logger.debug(f"GitHub sync skipped: {e}")
    
    return save_success


def update_story_title(book_slug: str, old_title: str, new_title: str) -> bool:
    """
    Update story title in JSON, database, and all references.
    
    Propagates the title change to:
    - story_positions.json
    - stories_dict.json
    - codex_tree.json
    - Database (if enabled)
    - Document store
    
    Args:
        book_slug: The book identifier
        old_title: Current story title
        new_title: New story title
    
    Returns:
        True if update succeeded, False otherwise
    """
    # Lazy imports to avoid circular dependencies
    from tree import load_codex_tree, save_codex_tree_to_json
    from utils.cache import invalidate_cache
    
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
        app_state.story_positions[book_slug] = positions
   
    # Update stories_dict cache
    if old_title in app_state.stories_dict:
        story_data = app_state.stories_dict.pop(old_title)
        story_data["title"] = new_title
        app_state.stories_dict[new_title] = story_data
   
    # Save to JSON files
    save_success = save_story_positions(book_slug)
    
    # Also save stories_dict.json
    try:
        with open(app_state.stories_dict_path, "w") as f:
            json.dump(app_state.stories_dict, f, indent=4, sort_keys=True)
    except Exception as e:
        logger.error(f"Failed to save stories_dict.json: {e}")
   
    # Update database if available
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            from models import Story
            with app_state.SessionLocal() as db:
                story = db.query(Story).filter_by(title=old_title, book_slug=book_slug).first()
                if story:
                    story.title = new_title
                    db.commit()
                    logger.info(f"Updated story title in database: '{old_title}' -> '{new_title}'")
                else:
                    logger.warning(f"Story '{old_title}' not found in database")
        except Exception as e:
            logger.error(f"Failed to update database title for '{old_title}': {e}")
            return False
   
    # Update document store metadata (handles both legacy and direct engines)
    _update_document_store_metadata(old_title, new_title)

    # Invalidate cache since data changed
    invalidate_cache()
    logger.info(f"Invalidated cache after updating title from '{old_title}' to '{new_title}'")

    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_story_title_change
        on_story_title_change(book_slug, old_title, new_title)
    except Exception as e:
        logger.debug(f"GitHub sync skipped: {e}")

    return True
