# backend/routes/stories.py
"""
Story CRUD routes for the Lexicon API.

Endpoints:
- POST /api/render-story - Render story HTML (static or book context)
- POST /api/update-boundaries - Update story character boundaries (editor)
- POST /api/update-title - Rename a story (editor)
- POST /api/update-keywords - Update story keywords (editor)
- POST /api/add-story - Add new story with immediate indexing (editor)
- DELETE /api/delete-story/{title} - Delete story from all systems (editor)
"""

import os
import logging
from typing import Dict

from fastapi import APIRouter, Depends

from .dependencies import (
    RenderQuery, UpdateBoundariesBody, UpdateTitleBody,
    UpdateKeywordsBody, AddStoryBody, require_editor, BOOKS_DIR
)
from .errors import AppError, ErrorCode
from utils import (
    stories_dict, load_story_positions, story_positions, save_story_positions,
    update_story_boundaries, update_story_title, update_story_keywords,
    render_static_story, render_md_with_scroll_and_highlight,
    find_paths_for_title, remove_from_path, save_codex_tree,
    load_pending_stories, save_pending_stories, invalidate_cache,
    get_cached_tree, load_full_md, check_story_overlap,
    find_book_slug, USE_DB, SessionLocal
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stories"])


@router.post("/render-story")
def render_story(body: RenderQuery):
    """
    Render story content as HTML.
    
    Modes:
    - "static": Just the story text with formatting
    - "book": Story highlighted within surrounding book context
    
    Optionally accepts start_char/end_char to override stored boundaries.
    """
    story = stories_dict.get(body.title)
    
    if not story:
        # Fallback: search by title across all books
        try:
            book_slug = find_book_slug(body.title)
            positions = load_story_positions(book_slug)
            pos = positions[body.title]
            story = {
                "title": body.title,
                "book_slug": book_slug,
                "pages": pos.get("pages", ""),
                "keywords": ", ".join(pos.get("keywords", [])),
                "start_char": pos.get("start_char", 0),
                "end_char": pos.get("end_char", 0),
            }
        except Exception:
            # Final fallback: check database
            if USE_DB and SessionLocal:
                try:
                    from models import Story
                    with SessionLocal() as db:
                        db_story = db.query(Story).filter_by(title=body.title).first()
                        if db_story:
                            story = {
                                "title": db_story.title,
                                "book_slug": db_story.book_slug,
                                "pages": db_story.pages or "",
                                "keywords": db_story.keywords or "",
                                "start_char": db_story.start_char or 0,
                                "end_char": db_story.end_char or 0,
                            }
                        else:
                            raise AppError(ErrorCode.NOT_FOUND_STORY, f"Story not found: {body.title}")
                except Exception as e:
                    log.error(f"Error querying database for story '{body.title}': {e}")
                    raise AppError(ErrorCode.NOT_FOUND_STORY, f"Story not found: {body.title}")
            else:
                raise AppError(ErrorCode.NOT_FOUND_STORY, f"Story not found: {body.title}")
    
    # Use provided boundaries if available
    start_char = body.start_char if body.start_char is not None else story["start_char"]
    end_char = body.end_char if body.end_char is not None else story["end_char"]
    
    if body.mode == "static":
        modified_story = {**story, "start_char": start_char, "end_char": end_char}
        return {"html": render_static_story(modified_story)}
    else:  # book mode
        html = render_md_with_scroll_and_highlight(
            book_slug=story["book_slug"],
            start_char=start_char,
            end_char=end_char,
            page=story["pages"].split("-")[0],
            search_query=body.search_query,
        )
        return {"html": html}


@router.post("/update-boundaries")
def update_boundaries(body: UpdateBoundariesBody, user=Depends(require_editor)):
    """Update story character boundaries. Editor only."""
    success = update_story_boundaries(
        book_slug=body.book_slug,
        title=body.title,
        start_char=body.start_char,
        end_char=body.end_char
    )
    if success:
        return {"status": "updated", "message": f"Boundaries updated for {body.title}"}
    else:
        raise AppError(ErrorCode.OPERATION_UPDATE_FAILED, f"Failed to update boundaries for {body.title}")


@router.post("/update-title")
def update_title(body: UpdateTitleBody, user=Depends(require_editor)):
    """Rename a story. Editor only."""
    success = update_story_title(
        book_slug=body.book_slug,
        old_title=body.old_title,
        new_title=body.new_title
    )
    if success:
        return {"status": "updated", "message": f"Title updated from '{body.old_title}' to '{body.new_title}'"}
    else:
        raise AppError(ErrorCode.OPERATION_UPDATE_FAILED, f"Failed to update title from '{body.old_title}' to '{body.new_title}'")


@router.post("/update-keywords")
def update_keywords(body: UpdateKeywordsBody, user=Depends(require_editor)):
    """Update story keywords. Editor only."""
    success = update_story_keywords(
        book_slug=body.book_slug,
        title=body.title,
        keywords=body.keywords
    )
    if success:
        return {"status": "updated", "message": f"Keywords updated for '{body.title}'"}
    else:
        raise AppError(ErrorCode.OPERATION_UPDATE_FAILED, f"Failed to update keywords for '{body.title}'")


@router.post("/add-story")
def add_story(body: AddStoryBody, user=Depends(require_editor)):
    """
    Add a new story to a book and immediately index it for search.
    
    Validates:
    - Book exists
    - Character positions are valid
    - No duplicate title in same book
    - Checks for overlaps (returns warning if found, unless force_overlap=True)
    
    On success, story is immediately searchable.
    """
    try:
        # 1. Validate book exists
        book_path = os.path.join(BOOKS_DIR, body.book_slug)
        if not os.path.isdir(book_path):
            raise AppError(ErrorCode.NOT_FOUND_BOOK, f"Book not found: {body.book_slug}")
        
        # 2. Load full text
        full_md = load_full_md(body.book_slug)
        if not full_md:
            raise AppError(ErrorCode.NOT_FOUND_FILE, f"Full_Text.md not found for {body.book_slug}")
        
        # 3. Validate positions
        if body.start_char < 0 or body.end_char > len(full_md):
            raise AppError(ErrorCode.VALIDATION_OUT_OF_BOUNDS, f"Character positions out of bounds (0-{len(full_md)})")
        
        if body.end_char <= body.start_char:
            raise AppError(ErrorCode.VALIDATION_INVALID_INPUT, "end_char must be greater than start_char")
        
        # 4. Extract and validate story text
        story_text = full_md[body.start_char:body.end_char].strip()
        if not story_text:
            raise AppError(ErrorCode.VALIDATION_INVALID_INPUT, "Story text is empty")
        
        if len(story_text) < 50:
            raise AppError(ErrorCode.VALIDATION_CONTENT_TOO_SHORT, f"Story too short ({len(story_text)} chars). Minimum 50 characters.")
        
        # 5. Check for duplicate title
        positions = load_story_positions(body.book_slug)
        if body.title in positions:
            raise AppError(ErrorCode.VALIDATION_DUPLICATE_TITLE, f"Story title '{body.title}' already exists in {body.book_slug}")
        
        # 6. Check for overlaps
        has_overlap, overlaps = check_story_overlap(body.book_slug, body.start_char, body.end_char)
        
        if has_overlap and not body.force_overlap:
            return {
                "status": "overlap_warning",
                "message": "Story overlaps with existing stories",
                "overlaps": overlaps,
                "requires_confirmation": True
            }
        
        # 7. Parse keywords
        keywords_list = [k.strip() for k in body.keywords.split(",") if k.strip()]
        
        # 8. Update story_positions.json
        positions[body.title] = {
            "start_char": body.start_char,
            "end_char": body.end_char,
            "pages": body.pages,
            "keywords": keywords_list
        }
        story_positions[body.book_slug] = positions
        if not save_story_positions(body.book_slug):
            raise AppError(ErrorCode.OPERATION_FAILED, "Failed to save story_positions.json")
        
        log.info(f"Saved story '{body.title}' to story_positions.json")
        
        # 9. Add to database
        if USE_DB and SessionLocal:
            try:
                with SessionLocal() as db:
                    from models import Story, Book
                    book = db.query(Book).filter_by(slug=body.book_slug).first()
                    if book:
                        story = Story(
                            title=body.title,
                            book_id=book.id,
                            book_slug=body.book_slug,
                            pages=body.pages,
                            keywords=",".join(keywords_list),
                            start_char=body.start_char,
                            end_char=body.end_char
                        )
                        db.add(story)
                        db.commit()
                        log.info(f"Added story '{body.title}' to database")
            except Exception as e:
                log.error(f"Failed to add story to database: {e}")
        
        # 10. Immediate indexing
        log.info(f"Embedding story '{body.title}' immediately...")
        from search import USE_DIRECT_SEARCH
        import numpy as np
        
        if USE_DIRECT_SEARCH:
            from search.engine import get_search_engine
            from search.models import StoryDocument
            
            engine = get_search_engine()
            doc_id = f"{body.book_slug}_{hash(body.title) & 0xFFFFFFFF}"
            story_doc = StoryDocument(
                id=doc_id,
                content=story_text,
                meta={
                    "type": "story",
                    "title": body.title,
                    "book": body.book_slug,
                    "source": body.book_slug.replace('_', ' '),
                    "pages": body.pages,
                    "keywords": ", ".join(keywords_list),
                    "start_char": body.start_char,
                    "end_char": body.end_char
                },
                embedding=None
            )
            engine.add_document(story_doc)
            engine.save()
            log.info(f"Story '{body.title}' added to Direct search engine")
        else:
            # Legacy Haystack
            from haystack import Document
            from utils import embedder_doc, document_store, document_store_path
            
            story_doc = Document(
                content=story_text,
                meta={
                    "type": "story",
                    "title": body.title,
                    "book": body.book_slug,
                    "source": body.book_slug.replace('_', ' '),
                    "pages": body.pages,
                    "keywords": ", ".join(keywords_list),
                    "start_char": body.start_char,
                    "end_char": body.end_char
                }
            )
            result = embedder_doc.run([story_doc])
            embedded_doc = result["documents"][0]
            
            if embedded_doc.embedding is not None and isinstance(embedded_doc.embedding, np.ndarray):
                embedded_doc.embedding = embedded_doc.embedding.tolist()
            
            document_store.write_documents([embedded_doc])
            
            all_docs = list(document_store.filter_documents({}))
            for doc in all_docs:
                if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                    doc.embedding = doc.embedding.tolist()
            
            document_store.save_to_disk(document_store_path)
            log.info(f"Story '{body.title}' added to Haystack document store")
        
        # 11. Update stories_dict cache
        stories_dict[body.title] = {
            "title": body.title,
            "book_slug": body.book_slug,
            "pages": body.pages,
            "keywords": ", ".join(keywords_list),
            "start_char": body.start_char,
            "end_char": body.end_char
        }
        
        # 12. Invalidate cache
        invalidate_cache()
        
        # 13. Auto-sync to GitHub
        try:
            from sync.github_sync import on_story_added
            on_story_added(body.book_slug, body.title)
        except Exception as e:
            log.debug(f"GitHub sync skipped: {e}")
        
        log.info(f"Story '{body.title}' added by {user.get('email')} and is now searchable!")
        
        return {
            "status": "success",
            "message": f"Story '{body.title}' saved and indexed successfully. It is now searchable!",
            "story": {
                "title": body.title,
                "book_slug": body.book_slug,
                "pages": body.pages,
                "start_char": body.start_char,
                "end_char": body.end_char,
                "length": len(story_text),
                "indexed": True
            },
            "overlap_warnings": [f"{o['title']} ({o['overlap_percent']}% overlap)" for o in overlaps] if has_overlap else []
        }
        
    except AppError:
        raise
    except Exception as e:
        log.error(f"Failed to add story: {e}", exc_info=True)
        raise AppError(ErrorCode.OPERATION_FAILED, "Failed to add story", detail=str(e))


@router.delete("/delete-story/{title}")
def delete_story(title: str, user=Depends(require_editor)):
    """
    Delete a story from all systems:
    - story_positions.json
    - Database
    - Search index (FAISS/FTS5 or Haystack)
    - Codex tree assignments
    - Pending queue
    """
    try:
        log.info(f"Deleting story '{title}' requested by {user.get('email')}")
        
        # 1. Find which book this story belongs to
        book_slug = None
        for slug, positions in story_positions.items():
            if title in positions:
                book_slug = slug
                break
        
        if not book_slug:
            raise AppError(ErrorCode.NOT_FOUND_STORY, f"Story '{title}' not found in any book")
        
        # 2. Remove from story_positions.json
        positions = load_story_positions(book_slug)
        if title in positions:
            del positions[title]
            story_positions[book_slug] = positions
            save_story_positions(book_slug)
            log.info(f"Removed '{title}' from story_positions.json for {book_slug}")
        
        # 3. Remove from stories_dict cache
        if title in stories_dict:
            del stories_dict[title]
        
        # 4. Remove from database
        if USE_DB and SessionLocal:
            try:
                with SessionLocal() as db:
                    from models import Story
                    story = db.query(Story).filter_by(title=title).first()
                    if story:
                        db.delete(story)
                        db.commit()
                        log.info(f"Deleted story '{title}' from database")
            except Exception as e:
                log.error(f"Failed to delete from database: {e}")
        
        # 5. Remove from search engine
        from search import USE_DIRECT_SEARCH
        
        if USE_DIRECT_SEARCH:
            try:
                from search.engine import get_search_engine
                engine = get_search_engine()
                deleted = engine.delete_by_title(title)
                if deleted:
                    log.info(f"Removed '{title}' from Direct search engine ({deleted} entries)")
                engine.save()
            except Exception as e:
                log.error(f"Failed to remove from Direct search engine: {e}")
        else:
            try:
                from utils import document_store, document_store_path
                import numpy as np
                
                docs = document_store.filter_documents({"field": "meta.title", "operator": "==", "value": title})
                if docs:
                    doc_ids = [doc.id for doc in docs]
                    document_store.delete_documents(doc_ids)
                    
                    all_docs = list(document_store.filter_documents({}))
                    docs_to_update = []
                    for doc in all_docs:
                        if doc.embedding is not None and isinstance(doc.embedding, np.ndarray):
                            doc.embedding = doc.embedding.tolist()
                            docs_to_update.append(doc)
                    
                    if docs_to_update:
                        document_store.delete_documents([doc.id for doc in docs_to_update])
                        document_store.write_documents(docs_to_update)
                    
                    document_store.save_to_disk(document_store_path)
                    log.info(f"Removed '{title}' from Haystack document store")
            except Exception as e:
                log.error(f"Failed to remove from Haystack document store: {e}")
        
        # 6. Remove from codex tree
        try:
            tree = get_cached_tree()
            paths = find_paths_for_title(tree, title)
            if paths:
                for path in paths:
                    tree = remove_from_path(tree, path, title)
                save_codex_tree(tree)
                log.info(f"Removed '{title}' from {len(paths)} category assignments")
        except Exception as e:
            log.error(f"Failed to remove from codex tree: {e}")
        
        # 7. Remove from pending queue
        try:
            pending = load_pending_stories()
            original_count = len(pending)
            pending = [p for p in pending if p.get("title") != title]
            if len(pending) < original_count:
                save_pending_stories(pending)
                log.info(f"Removed '{title}' from pending queue")
        except Exception as e:
            log.error(f"Failed to remove from pending queue: {e}")
        
        # 8. Invalidate cache
        invalidate_cache()
        
        # 9. Auto-sync to GitHub
        try:
            from sync.github_sync import on_story_deleted
            on_story_deleted(book_slug, title)
        except Exception as e:
            log.debug(f"GitHub sync skipped: {e}")
        
        log.info(f"Successfully deleted story '{title}' from {book_slug}")
        
        return {
            "status": "success",
            "message": f"Story '{title}' deleted successfully",
            "book_slug": book_slug
        }
        
    except AppError:
        raise
    except Exception as e:
        log.error(f"Failed to delete story: {e}", exc_info=True)
        raise AppError(ErrorCode.OPERATION_DELETE_FAILED, f"Failed to delete story '{title}'", detail=str(e))
