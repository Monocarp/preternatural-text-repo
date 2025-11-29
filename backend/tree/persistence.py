# backend/tree/persistence.py
"""
Tree persistence - Loading and saving the codex tree.

Handles:
- Loading tree from database or JSON fallback
- Saving tree to JSON and database
- JSON file operations
"""

import os
import json
import time
import logging

from state import app_state
from models import CodexNode, NodeStory, Story
from .operations import CATEGORIES, merge_trees

logger = logging.getLogger(__name__)


def load_codex_tree_from_json() -> dict:
    """
    Load codex tree from JSON file, creating default if needed.
    
    Returns:
        The tree dictionary
    """
    if os.path.exists(app_state.codex_tree_path):
        with open(app_state.codex_tree_path, "r", encoding="utf-8-sig") as f:
            tree = json.load(f)
    else:
        tree = CATEGORIES.copy()
        
        def ensure_lists(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    ensure_lists(v)
                else:
                    d[k] = []
        
        ensure_lists(tree)
        save_codex_tree_to_json(tree)
    
    return tree


def save_codex_tree_to_json(tree: dict) -> None:
    """
    Save codex tree to JSON file.
    
    Args:
        tree: The tree dictionary to save
    """
    with open(app_state.codex_tree_path, "w") as f:
        json.dump(tree, f, indent=4, sort_keys=True)


def insert_recursive(tree_json: dict, db, parent_id: int = None) -> None:
    """
    Recursively insert tree nodes into database.
    
    Args:
        tree_json: Tree structure to insert
        db: Database session
        parent_id: Parent node ID (None for root nodes)
    """
    for name, value in tree_json.items():
        node = CodexNode(name=name, parent_id=parent_id)
        db.add(node)
        db.flush()  # Get ID
        
        if isinstance(value, list):
            for title in value:
                story = db.query(Story).filter_by(title=title).first()
                if story:
                    db.add(NodeStory(node_id=node.id, story_id=story.id))
        elif isinstance(value, dict):
            insert_recursive(value, db, node.id)


def load_codex_tree() -> dict:
    """
    Load codex tree from database or JSON fallback.
    
    This is a lightweight operation that builds the tree from the database.
    It does NOT sync from disk - that's done by sync_disk_to_db().
    
    Returns:
        The codex tree dictionary
    """
    logger.info("Building codex tree...")
    start_time = time.monotonic()

    # Fallback if no DB - load from JSON
    if not app_state.USE_DB or app_state.SessionLocal is None:
        logger.info("Using JSON fallback for codex tree")
        tree = load_codex_tree_from_json()
        
        # Ensure stories_dict is loaded
        if not app_state.stories_dict:
            try:
                with open(app_state.stories_dict_path, "r") as f:
                    app_state.stories_dict.update(json.load(f))
            except FileNotFoundError:
                logger.warning("stories_dict.json not found")
        
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded tree from JSON in {elapsed:.2f}s")
        return tree
   
    try:
        with app_state.SessionLocal() as db:
            root_nodes = db.query(CodexNode).filter_by(parent_id=None).all()
            
            if not root_nodes:
                logger.info("No codex nodes in DB - initializing from CATEGORIES")
                tree_json = load_codex_tree_from_json()
                insert_recursive(tree_json, db)
                db.commit()
                root_nodes = db.query(CodexNode).filter_by(parent_id=None).all()
           
            # Eagerly load all nodes with relationships
            from sqlalchemy.orm import selectinload
           
            all_nodes = db.query(CodexNode).options(
                selectinload(CodexNode.stories),
                selectinload(CodexNode.children).selectinload(CodexNode.stories),
                selectinload(CodexNode.children).selectinload(CodexNode.children).selectinload(CodexNode.stories),
                selectinload(CodexNode.children).selectinload(CodexNode.children).selectinload(CodexNode.children).selectinload(CodexNode.stories)
            ).all()
           
            # Create lookup and rebuild parent-child relationships
            nodes_by_id = {node.id: node for node in all_nodes}
            for node in all_nodes:
                if node.parent_id and node.parent_id in nodes_by_id:
                    parent = nodes_by_id[node.parent_id]
                    if node not in parent.children:
                        parent.children.append(node)
           
            root_nodes_loaded = [node for node in all_nodes if node.parent_id is None]
           
            def build_tree(node):
                """Build tree structure from database node"""
                try:
                    story_titles = [s.title for s in node.stories] if node.stories else []
                    children_list = list(node.children) if node.children else []
                    
                    logger.debug(f"Node '{node.name}': {len(story_titles)} stories, {len(children_list)} children")
                except Exception as e:
                    logger.error(f"Error building tree for node '{node.name}': {e}")
                    return {node.name: {}}
               
                if story_titles and not children_list:
                    return {node.name: story_titles}
                else:
                    tree = {node.name: {}}
                    if story_titles:
                        tree[node.name]['_stories'] = story_titles
                   
                    for child in children_list:
                        child_tree = build_tree(child)
                        for child_key, child_value in child_tree.items():
                            if child_key in tree[node.name]:
                                logger.warning(f"Duplicate child '{child_key}' under '{node.name}'")
                                continue
                            tree[node.name][child_key] = child_value
               
                return tree
           
            tree = {}
            for root in root_nodes_loaded:
                root_tree = build_tree(root)
                for root_key, root_value in root_tree.items():
                    if root_key in tree:
                        tree[root_key] = merge_trees(tree[root_key], root_value)
                    else:
                        tree[root_key] = root_value
           
            # Count total story assignments
            def count_stories(t):
                count = 0
                if isinstance(t, dict):
                    for k, v in t.items():
                        if k == '_stories':
                            count += len(v) if isinstance(v, list) else 0
                        else:
                            count += count_stories(v)
                elif isinstance(t, list):
                    count += len(t)
                return count
           
            total_stories = count_stories(tree)
            save_codex_tree_to_json(tree)
            
            elapsed = time.monotonic() - start_time
            logger.info(f"Built tree from DB with {total_stories} assignments in {elapsed:.2f}s")
            return tree
            
    except Exception as e:
        logger.error(f"Error loading codex tree from database: {e}. Falling back to JSON.")
        tree = load_codex_tree_from_json()
        
        if not app_state.stories_dict:
            try:
                with open(app_state.stories_dict_path, "r") as f:
                    app_state.stories_dict.update(json.load(f))
            except FileNotFoundError:
                pass
        
        elapsed = time.monotonic() - start_time
        logger.info(f"Loaded tree from JSON fallback in {elapsed:.2f}s")
        return tree


def save_codex_tree(tree: dict) -> None:
    """
    Save codex tree to JSON file and database (if available).
    
    Also optionally commits to HuggingFace if HF_TOKEN is set.
    
    Args:
        tree: The tree dictionary to save
    """
    from utils.cache import invalidate_cache
    from huggingface_hub import HfApi
    
    os.makedirs(app_state.data_dir, exist_ok=True)
    
    logger.info("Saving codex tree...")
   
    # Always save to JSON
    save_codex_tree_to_json(tree)
   
    # Also save stories_dict if it exists
    if app_state.stories_dict:
        with open(app_state.stories_dict_path, "w") as f:
            json.dump(app_state.stories_dict, f, indent=4, sort_keys=True)
   
    # Save to database if available
    if app_state.USE_DB and app_state.SessionLocal:
        try:
            with app_state.SessionLocal() as db:
                from sqlalchemy.orm import selectinload
               
                def save_tree_to_db(node_dict, parent_id=None):
                    """Recursively save tree structure to database"""
                    for name, value in node_dict.items():
                        if name == '_stories':
                            continue
                       
                        # Find or create node
                        query = db.query(CodexNode).filter_by(name=name)
                        if parent_id:
                            query = query.filter_by(parent_id=parent_id)
                        else:
                            query = query.filter_by(parent_id=None)
                        node = query.first()
                       
                        if not node:
                            node = CodexNode(name=name, parent_id=parent_id)
                            db.add(node)
                            db.flush()
                       
                        # Get current stories for this node
                        fresh_node = db.query(CodexNode).options(
                            selectinload(CodexNode.stories)
                        ).filter_by(id=node.id).first()
                        current_story_ids = {s.id for s in fresh_node.stories} if fresh_node and fresh_node.stories else set()
                       
                        # Determine expected story titles
                        expected_titles = set()
                        if isinstance(value, list):
                            expected_titles = set(value)
                        elif isinstance(value, dict) and '_stories' in value:
                            expected_titles = set(value['_stories'])
                       
                        # Add missing story relationships
                        for title in expected_titles:
                            story = db.query(Story).filter_by(title=title).first()
                            if story and story.id not in current_story_ids:
                                db.add(NodeStory(node_id=node.id, story_id=story.id))
                                logger.debug(f"Added story '{title}' to node '{name}'")
                       
                        # Recursively process children
                        if isinstance(value, dict):
                            save_tree_to_db(value, node.id)
               
                save_tree_to_db(tree)
                db.commit()
                logger.info("Saved codex tree to database")
        except Exception as e:
            logger.error(f"Error saving codex tree to database: {e}")
    
    # Invalidate cache after saving
    invalidate_cache()
   
    # Optional auto-commit to HuggingFace
    token = os.getenv("HF_TOKEN")
    if token:
        try:
            api = HfApi(token=token)
            api.upload_file(
                path_or_fileobj=app_state.codex_tree_path,
                path_in_repo=app_state.codex_tree_path,
                repo_id="hetzerdj/preternatural-text-ui",
                repo_type="space"
            )
            if app_state.stories_dict:
                api.upload_file(
                    path_or_fileobj=app_state.stories_dict_path,
                    path_in_repo=app_state.stories_dict_path,
                    repo_id="hetzerdj/preternatural-text-ui",
                    repo_type="space"
                )
            logger.info("Auto-committed to HF repo")
        except Exception as e:
            logger.error(f"Auto-commit failed: {e}")
    
    # Auto-commit to GitHub (for local dev sync)
    try:
        from sync.github_sync import sync_codex_tree
        sync_codex_tree("Update category tree")
    except Exception as e:
        logger.debug(f"GitHub sync skipped: {e}")

