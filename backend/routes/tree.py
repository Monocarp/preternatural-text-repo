# backend/routes/tree.py
"""
Codex tree routes for the Lexicon API.

Endpoints:
- GET /api/get-tree - Get full category tree
- GET /api/get-stories/{path} - Get stories at a tree path
- GET /api/get-unassigned - Get stories not assigned to any category
- POST /api/assign-category - Assign story to category (editor only)
- DELETE /api/remove-category - Remove story from category (editor only)
- POST /api/create-category - Create new category/subcategory (editor only)
- DELETE /api/delete-category - Delete category/subcategory (editor only)
- GET /api/category-info/{path} - Get category metadata
"""

import logging
import urllib.parse
import json
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Depends

from .dependencies import AssignBody, RemoveBody, CreateCategoryBody, DeleteCategoryBody, RenameCategoryBody, MoveCategoryBody, require_editor
from utils import (
    get_cached_tree, get_stories_at_path, invalidate_cache,
    assign_to_path, remove_from_path, save_codex_tree_to_json,
    stories_dict, stories_dict_path, enrich_stories_with_book_metadata
)
from utils.cache import get_assigned_titles_set
from tree.operations import create_category, delete_category, get_category_info, rename_category, move_category

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
def get_unassigned(book_slug: str = None):
    """
    Get all stories not assigned to any category.
    
    Args:
        book_slug: Optional book slug to filter unassigned stories by book
    """
    assigned = get_assigned_titles_set()
    unassigned = [s for t, s in stories_dict.items() if t not in assigned]
    
    # Filter by book if specified
    if book_slug:
        unassigned = [s for s in unassigned if s.get('book_slug') == book_slug]
    
    return enrich_stories_with_book_metadata(unassigned)


@router.get("/story-assignments/{title:path}")
def get_story_assignments(title: str):
    """
    Get all category paths where a story is assigned.
    
    Args:
        title: URL-encoded story title
    
    Returns:
        {"paths": [["Category", "Subcategory"], ...]}
    """
    from tree.queries import find_story_assignments
    
    decoded_title = urllib.parse.unquote(title)
    tree = get_cached_tree()
    paths = find_story_assignments(tree, decoded_title)
    return {"title": decoded_title, "paths": paths}


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


@router.post("/create-category")
def create_category_endpoint(body: CreateCategoryBody, user: Dict = Depends(require_editor)):
    """
    Create a new category or subcategory.
    
    Creates the category in both database (if enabled) and JSON file.
    
    Args:
        body.parent_path: Path to parent category (empty list for root-level)
        body.name: Name of the new category
    """
    from utils import USE_DB, SessionLocal
    from models import CodexNode
    
    tree = get_cached_tree()
    
    # Validate and create in tree
    try:
        updated_tree = create_category(tree, body.parent_path, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Update database if enabled
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            # Navigate to parent node
            parent_id = None
            if body.parent_path:
                for level_name in body.parent_path:
                    query = db.query(CodexNode).filter_by(name=level_name)
                    if parent_id:
                        query = query.filter_by(parent_id=parent_id)
                    else:
                        query = query.filter_by(parent_id=None)
                    parent_node = query.first()
                    
                    if not parent_node:
                        # Create missing parent nodes
                        parent_node = CodexNode(name=level_name, parent_id=parent_id)
                        db.add(parent_node)
                        db.flush()
                        log.info(f"Created missing parent node '{level_name}' in database")
                    
                    parent_id = parent_node.id
            
            # Check if category already exists in DB
            existing = db.query(CodexNode).filter_by(name=body.name, parent_id=parent_id).first()
            if existing:
                log.warning(f"Category '{body.name}' already exists in database, skipping DB insert")
            else:
                new_node = CodexNode(name=body.name, parent_id=parent_id)
                db.add(new_node)
                db.commit()
                log.info(f"Created category '{body.name}' in database")
    
    # Save to JSON
    save_codex_tree_to_json(updated_tree)
    invalidate_cache()
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_created
        on_category_created(body.name, body.parent_path)
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")
    
    return {
        "status": "created",
        "path": body.parent_path + [body.name]
    }


@router.delete("/delete-category")
def delete_category_endpoint(body: DeleteCategoryBody, user: Dict = Depends(require_editor)):
    """
    Delete a category or subcategory.
    
    Removes the category from both database (if enabled) and JSON file.
    Stories assigned to this category will be unassigned from it.
    
    Args:
        body.path: Full path to the category to delete
    """
    from utils import USE_DB, SessionLocal
    from models import CodexNode, NodeStory
    
    tree = get_cached_tree()
    
    # Get info before deletion
    info = get_category_info(tree, body.path)
    if not info.get('exists'):
        raise HTTPException(status_code=404, detail=f"Category not found: {'/'.join(body.path)}")
    
    # Delete from tree
    try:
        updated_tree, affected_stories = delete_category(tree, body.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Update database if enabled
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            # Find the node to delete
            parent_id = None
            target_node = None
            
            for level_name in body.path:
                query = db.query(CodexNode).filter_by(name=level_name)
                if parent_id:
                    query = query.filter_by(parent_id=parent_id)
                else:
                    query = query.filter_by(parent_id=None)
                target_node = query.first()
                
                if not target_node:
                    log.warning(f"Node '{level_name}' not found in database")
                    break
                
                parent_id = target_node.id
            
            if target_node:
                # Recursively delete node and children
                def delete_node_recursive(node_id):
                    # Delete all NodeStory associations for this node
                    db.query(NodeStory).filter_by(node_id=node_id).delete()
                    
                    # Find and delete children
                    children = db.query(CodexNode).filter_by(parent_id=node_id).all()
                    for child in children:
                        delete_node_recursive(child.id)
                    
                    # Delete the node itself
                    db.query(CodexNode).filter_by(id=node_id).delete()
                
                delete_node_recursive(target_node.id)
                db.commit()
                log.info(f"Deleted category '{body.path[-1]}' and children from database")
    
    # Save to JSON
    save_codex_tree_to_json(updated_tree)
    invalidate_cache()
    
    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_deleted
        on_category_deleted(body.path[-1], body.path[:-1] if len(body.path) > 1 else [])
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")
    
    return {
        "status": "deleted",
        "affected_stories": affected_stories,
        "story_count": len(affected_stories),
        "had_children": info.get('has_children', False)
    }


@router.post("/rename-category")
def rename_category_endpoint(body: RenameCategoryBody, user: Dict = Depends(require_editor)):
    """
    Rename a category or subcategory.

    Preserves all stories and children under the node — only the name changes.
    Updates both database (if enabled) and JSON file.

    Args:
        body.path: Full path to the category to rename
        body.new_name: The new name for the category
    """
    from utils import USE_DB, SessionLocal
    from models import CodexNode

    tree = get_cached_tree()

    # Validate and rename in tree
    try:
        updated_tree = rename_category(tree, body.path, body.new_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    old_name = body.path[-1]

    # Update database if enabled
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            # Navigate to the node
            parent_id = None
            target_node = None

            for level_name in body.path:
                query = db.query(CodexNode).filter_by(name=level_name)
                if parent_id:
                    query = query.filter_by(parent_id=parent_id)
                else:
                    query = query.filter_by(parent_id=None)
                target_node = query.first()

                if not target_node:
                    log.warning(f"Node '{level_name}' not found in database for path: {body.path}")
                    break

                parent_id = target_node.id

            if target_node:
                target_node.name = body.new_name
                db.commit()
                log.info(f"Renamed DB node '{old_name}' -> '{body.new_name}'")

    # Save to JSON
    save_codex_tree_to_json(updated_tree)
    invalidate_cache()

    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_renamed
        on_category_renamed(old_name, body.new_name, body.path[:-1])
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")

    return {
        "status": "renamed",
        "old_name": old_name,
        "new_name": body.new_name,
        "path": body.path[:-1] + [body.new_name],
    }


@router.post("/move-category")
def move_category_endpoint(body: MoveCategoryBody, user: Dict = Depends(require_editor)):
    """
    Move a category (with all children and stories) to a new parent.

    Atomically updates both the database and codex_tree.json.

    Args:
        body.source_path: Full path to the category to move
        body.dest_parent_path: Full path to the destination parent ([] = root level)
    """
    from utils import USE_DB, SessionLocal
    from models import CodexNode

    if not body.source_path:
        raise HTTPException(status_code=400, detail="source_path cannot be empty")

    tree = get_cached_tree()

    # Validate and move in tree
    try:
        updated_tree = move_category(tree, body.source_path, body.dest_parent_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    node_name = body.source_path[-1]

    # Update database if enabled
    if USE_DB and SessionLocal:
        with SessionLocal() as db:
            # Find the node to move
            parent_id = None
            target_node = None
            for level_name in body.source_path:
                query = db.query(CodexNode).filter_by(name=level_name)
                query = query.filter_by(parent_id=parent_id)
                target_node = query.first()
                if not target_node:
                    log.warning(f"Node '{level_name}' not found in DB for source path")
                    break
                parent_id = target_node.id

            # Find destination parent node
            new_parent_id = None
            if body.dest_parent_path:
                for level_name in body.dest_parent_path:
                    query = db.query(CodexNode).filter_by(name=level_name)
                    query = query.filter_by(parent_id=new_parent_id)
                    dest_node = query.first()
                    if not dest_node:
                        log.warning(f"Destination node '{level_name}' not found in DB")
                        dest_node = None
                        break
                    new_parent_id = dest_node.id

            if target_node:
                target_node.parent_id = new_parent_id
                db.commit()
                log.info(
                    f"Moved DB node '{node_name}' to parent_id={new_parent_id} "
                    f"({'root' if new_parent_id is None else '/'.join(body.dest_parent_path)})"
                )

    # Save to JSON
    save_codex_tree_to_json(updated_tree)
    invalidate_cache()

    # Auto-sync to GitHub
    try:
        from sync.github_sync import on_category_moved
        on_category_moved(node_name, body.source_path[:-1], body.dest_parent_path)
    except Exception as e:
        log.debug(f"GitHub sync skipped: {e}")

    return {
        "status": "moved",
        "node": node_name,
        "from": body.source_path[:-1],
        "to": body.dest_parent_path + [node_name],
    }


@router.get("/category-info/{path:path}")
def get_category_info_endpoint(path: str):
    """
    Get information about a category.
    
    Args:
        path: URL-encoded path like "Demonic%20Activity/Obsession"
    
    Returns dict with: exists, has_children, has_stories, story_count, child_count
    """
    parts = [urllib.parse.unquote(p.strip()) for p in path.split("/") if p.strip()]
    tree = get_cached_tree()
    
    return get_category_info(tree, parts)
