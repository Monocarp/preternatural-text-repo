# backend/routes/tree.py
"""
Codex tree routes for the Lexicon API.

Endpoints:
- GET /api/get-tree - Get full category tree
- GET /api/get-stories/{path} - Get stories at a tree path
- GET /api/get-unassigned - Get stories not assigned to any category
- POST /api/assign-category - Assign story to category (editor only)
- DELETE /api/remove-category - Remove story from category (editor only)
"""

import logging
import urllib.parse
import json
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Depends

from .dependencies import AssignBody, RemoveBody, require_editor
from utils import (
    get_cached_tree, get_stories_at_path, invalidate_cache,
    assign_to_path, remove_from_path, save_codex_tree_to_json,
    stories_dict, stories_dict_path, enrich_stories_with_book_metadata
)
from utils.cache import get_assigned_titles_set

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tree"])


@router.get("/get-tree")
def get_tree():
    """Get the full codex category tree structure."""
    return get_cached_tree()


@router.get("/get-stories/{path:path}")
def get_stories(path: str, subcats: Optional[str] = None):
    """
    Get stories assigned to a specific tree path.
    
    Args:
        path: URL-encoded path like "Demonic%20Activity/Obsession"
        subcats: Optional comma-separated list of subcategories to filter by
    
    Returns list of story objects with book metadata.
    """
    log.debug(f"Raw path received: {repr(path)}")
    parts = [urllib.parse.unquote(p.strip()) for p in path.split("/") if p.strip()]
    log.debug(f"After split and decode: {parts}")
    tree = get_cached_tree()
    
    if subcats:
        from tree.queries import get_stories_for_subcats
        subcat_list = [s.strip() for s in subcats.split(",") if s.strip()]
        log.debug(f"Filtering by subcategories: {subcat_list}")
        titles = get_stories_for_subcats(tree, parts, subcat_list)
        stories = [stories_dict[title] for title in titles if title in stories_dict]
        stories = enrich_stories_with_book_metadata(stories)
    else:
        stories = get_stories_at_path(tree, parts)
    
    log.debug(f"Found {len(stories)} stories for path {parts}")
    return stories


@router.get("/get-unassigned")
def get_unassigned():
    """Get all stories not assigned to any category."""
    assigned = get_assigned_titles_set()
    unassigned = [s for t, s in stories_dict.items() if t not in assigned]
    return enrich_stories_with_book_metadata(unassigned)


@router.post("/assign-category")
def assign_category(body: AssignBody, user: Dict = Depends(require_editor)):
    """
    Assign a story to a category path.
    
    Creates the category path if it doesn't exist.
    Updates both database (if enabled) and JSON file.
    """
    from utils import USE_DB, SessionLocal
    from models import Story, CodexNode, NodeStory
    
    # Update database if enabled
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            existing_story = db.query(Story).filter_by(title=body.story['title']).first()
            if not existing_story:
                db.add(Story(**body.story))
                db.commit()
                log.info(f"Created story {body.story['title']} in database")
            
            # Navigate to target node, creating as needed
            current_parent_id = None
            target_node = None
            
            for level_name in body.path:
                query = db.query(CodexNode).filter_by(name=level_name)
                if current_parent_id:
                    query = query.filter_by(parent_id=current_parent_id)
                else:
                    query = query.filter_by(parent_id=None)
                target_node = query.first()
                
                if not target_node:
                    target_node = CodexNode(name=level_name, parent_id=current_parent_id)
                    db.add(target_node)
                    db.flush()
                    log.info(f"Created node '{level_name}' in database")
                
                current_parent_id = target_node.id
            
            if target_node:
                story = db.query(Story).filter_by(title=body.story['title']).first()
                if story:
                    existing = db.query(NodeStory).filter_by(
                        node_id=target_node.id, story_id=story.id
                    ).first()
                    if not existing:
                        db.add(NodeStory(node_id=target_node.id, story_id=story.id))
                        db.commit()
                        log.info(f"Assigned story '{body.story['title']}' to node '{target_node.name}'")
    
    # Update in-memory tree and JSON
    tree = get_cached_tree()
    updated = assign_to_path(tree, body.path, body.story)
    save_codex_tree_to_json(updated)
    
    if stories_dict:
        with open(stories_dict_path, "w") as f:
            json.dump(stories_dict, f, indent=4, sort_keys=True)
    
    invalidate_cache()
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_change
        on_category_change("Assign", body.story['title'], body.path)
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")
    
    return {"status": "assigned"}


@router.delete("/remove-category")
def remove_category(body: RemoveBody, user: Dict = Depends(require_editor)):
    """
    Remove a story from a category path.
    
    Updates both database (if enabled) and JSON file.
    """
    from utils import USE_DB, SessionLocal
    from models import Story, CodexNode, NodeStory
    
    # Remove from database if enabled
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            current_parent_id = None
            target_node = None
            
            for level_name in body.path:
                query = db.query(CodexNode).filter_by(name=level_name)
                if current_parent_id:
                    query = query.filter_by(parent_id=current_parent_id)
                else:
                    query = query.filter_by(parent_id=None)
                target_node = query.first()
                
                if not target_node:
                    log.warning(f"Node '{level_name}' not found in database for path: {body.path}")
                    break
                
                current_parent_id = target_node.id
            
            if target_node:
                story = db.query(Story).filter_by(title=body.title).first()
                if story:
                    node_story = db.query(NodeStory).filter_by(
                        node_id=target_node.id, story_id=story.id
                    ).first()
                    if node_story:
                        db.delete(node_story)
                        db.commit()
                        log.info(f"Removed story '{body.title}' from node '{target_node.name}'")
    
    # Update in-memory tree and JSON
    tree = get_cached_tree()
    updated = remove_from_path(tree, body.path, body.title)
    save_codex_tree_to_json(updated)
    
    invalidate_cache()
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_change
        on_category_change("Remove", body.title, body.path)
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")
    
    return {"status": "removed"}
