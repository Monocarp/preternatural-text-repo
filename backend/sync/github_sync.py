# backend/sync/github_sync.py
"""
GitHub synchronization for production data changes.

Automatically commits changes to story data (boundaries, titles, deletions, 
category assignments) back to the GitHub repository so local development 
stays in sync with production.

Requires GITHUB_TOKEN environment variable with repo write access.
"""

import os
import json
import base64
import logging
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)

# Files that should be synced to GitHub when they change
SYNCABLE_FILES = [
    "data/codex_tree.json",
    "data/stories_dict.json",
]

# Pattern for book-specific files
BOOK_FILE_PATTERN = "books/{book_slug}/story_positions.json"


def get_github_config():
    """Get GitHub configuration from environment."""
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO", "Monocarp/preternatural-text-repo")
    branch = os.getenv("GITHUB_BRANCH", "main")
    
    return {
        "token": token,
        "repo": repo,
        "branch": branch,
        "enabled": bool(token)
    }


def _github_api_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make a request to the GitHub API."""
    import urllib.request
    import urllib.error
    
    config = get_github_config()
    if not config["enabled"]:
        raise ValueError("GITHUB_TOKEN not set")
    
    url = f"https://api.github.com/repos/{config['repo']}/{endpoint}"
    
    headers = {
        "Authorization": f"token {config['token']}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "preternatural-text-backend"
    }
    
    body = json.dumps(data).encode("utf-8") if data else None
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        logger.error(f"GitHub API error {e.code}: {error_body}")
        raise


def get_file_sha(file_path: str) -> Optional[str]:
    """Get the current SHA of a file in the GitHub repo (needed for updates)."""
    config = get_github_config()
    if not config["enabled"]:
        return None
    
    try:
        result = _github_api_request("GET", f"contents/{file_path}?ref={config['branch']}")
        return result.get("sha")
    except Exception as e:
        logger.debug(f"File {file_path} not found in repo (may be new): {e}")
        return None


def sync_file_to_github(
    local_path: str, 
    repo_path: str, 
    commit_message: str
) -> bool:
    """
    Sync a local file to GitHub.
    
    Args:
        local_path: Absolute path to the local file
        repo_path: Path in the repository (e.g., "data/codex_tree.json")
        commit_message: Commit message describing the change
    
    Returns:
        True if sync succeeded, False otherwise
    """
    config = get_github_config()
    
    if not config["enabled"]:
        logger.debug("GitHub sync disabled (no GITHUB_TOKEN)")
        return False
    
    try:
        # Read local file content
        with open(local_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Encode content as base64
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        # Get current file SHA (required for updates)
        sha = get_file_sha(repo_path)
        
        # Prepare commit data
        data = {
            "message": commit_message,
            "content": content_b64,
            "branch": config["branch"]
        }
        
        if sha:
            data["sha"] = sha
        
        # Create/update file via GitHub API
        result = _github_api_request("PUT", f"contents/{repo_path}", data)
        
        commit_sha = result.get("commit", {}).get("sha", "unknown")[:7]
        logger.info(f"Synced {repo_path} to GitHub (commit {commit_sha})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync {repo_path} to GitHub: {e}")
        return False


def sync_codex_tree(reason: str = "Update category assignments") -> bool:
    """Sync codex_tree.json to GitHub."""
    from state import app_state
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"[auto] {reason} ({timestamp})"
    
    return sync_file_to_github(
        local_path=app_state.codex_tree_path,
        repo_path="data/codex_tree.json",
        commit_message=commit_msg
    )


def sync_stories_dict(reason: str = "Update stories metadata") -> bool:
    """Sync stories_dict.json to GitHub."""
    from state import app_state
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"[auto] {reason} ({timestamp})"
    
    return sync_file_to_github(
        local_path=app_state.stories_dict_path,
        repo_path="data/stories_dict.json",
        commit_message=commit_msg
    )


def sync_document_store(reason: str = "Update document store") -> bool:
    """Sync document_store.json to GitHub (Haystack search index)."""
    from state import app_state
    
    local_path = os.path.join(app_state.data_dir, "document_store.json")
    
    if not os.path.exists(local_path):
        logger.warning(f"document_store.json not found at {local_path}")
        return False
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"[auto] {reason} ({timestamp})"
    
    return sync_file_to_github(
        local_path=local_path,
        repo_path="data/document_store.json",
        commit_message=commit_msg
    )


def sync_documents_json(reason: str = "Update documents") -> bool:
    """Sync documents.json to GitHub (Haystack documents)."""
    from state import app_state
    
    local_path = os.path.join(app_state.data_dir, "documents.json")
    
    if not os.path.exists(local_path):
        logger.warning(f"documents.json not found at {local_path}")
        return False
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"[auto] {reason} ({timestamp})"
    
    return sync_file_to_github(
        local_path=local_path,
        repo_path="data/documents.json",
        commit_message=commit_msg
    )


def sync_story_positions(book_slug: str, reason: str = "Update story positions") -> bool:
    """Sync a book's story_positions.json to GitHub."""
    from state import app_state
    
    local_path = os.path.join(app_state.books_dir, book_slug, "story_positions.json")
    repo_path = f"books/{book_slug}/story_positions.json"
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"[auto] {reason} for {book_slug} ({timestamp})"
    
    return sync_file_to_github(
        local_path=local_path,
        repo_path=repo_path,
        commit_message=commit_msg
    )


def sync_all_changed_files(
    book_slugs: List[str] = None,
    include_tree: bool = True,
    include_stories_dict: bool = True,
    reason: str = "Sync production changes"
) -> dict:
    """
    Sync multiple files to GitHub in one operation.
    
    Args:
        book_slugs: List of book slugs whose story_positions.json changed
        include_tree: Whether to sync codex_tree.json
        include_stories_dict: Whether to sync stories_dict.json
        reason: Description of the change
    
    Returns:
        Dictionary with sync results for each file
    """
    results = {}
    
    if include_tree:
        results["codex_tree.json"] = sync_codex_tree(reason)
    
    if include_stories_dict:
        results["stories_dict.json"] = sync_stories_dict(reason)
    
    if book_slugs:
        for slug in book_slugs:
            results[f"books/{slug}/story_positions.json"] = sync_story_positions(slug, reason)
    
    successes = sum(1 for v in results.values() if v)
    total = len(results)
    logger.info(f"GitHub sync complete: {successes}/{total} files synced")
    
    return results


# Convenience function for common operations
def on_story_boundary_change(book_slug: str, title: str):
    """Call after updating story boundaries."""
    sync_story_positions(book_slug, f"Update boundaries for '{title}'")
    sync_stories_dict(f"Update boundaries for '{title}'")


def on_story_title_change(book_slug: str, old_title: str, new_title: str):
    """Call after renaming a story."""
    sync_all_changed_files(
        book_slugs=[book_slug],
        include_tree=True,
        include_stories_dict=True,
        reason=f"Rename '{old_title}' to '{new_title}'"
    )


def on_story_keywords_change(book_slug: str, title: str):
    """Call after updating story keywords."""
    sync_story_positions(book_slug, f"Update keywords for '{title}'")
    sync_stories_dict(f"Update keywords for '{title}'")


def on_story_added(book_slug: str, title: str):
    """Call after adding a new story."""
    sync_story_positions(book_slug, f"Add story '{title}'")
    sync_stories_dict(f"Add story '{title}'")


def on_story_deleted(book_slug: str, title: str):
    """Call after deleting a story."""
    sync_all_changed_files(
        book_slugs=[book_slug],
        include_tree=True,
        include_stories_dict=True,
        reason=f"Delete story '{title}'"
    )
    # Also sync document store so search index persists
    sync_document_store(f"Delete story '{title}'")
    sync_documents_json(f"Delete story '{title}'")


def on_category_change(action: str, title: str, path: List[str]):
    """Call after assigning/removing a category."""
    path_str = " > ".join(path)
    sync_codex_tree(f"{action} '{title}' {'to' if action == 'Assign' else 'from'} {path_str}")


def on_category_created(name: str, parent_path: List[str]):
    """Call after creating a new category."""
    if parent_path:
        path_str = " > ".join(parent_path)
        sync_codex_tree(f"Create category '{name}' under {path_str}")
    else:
        sync_codex_tree(f"Create root category '{name}'")


def on_category_deleted(name: str, parent_path: List[str]):
    """Call after deleting a category."""
    if parent_path:
        path_str = " > ".join(parent_path)
        sync_codex_tree(f"Delete category '{name}' from {path_str}")
    else:
        sync_codex_tree(f"Delete root category '{name}'")


def on_category_renamed(old_name: str, new_name: str, parent_path: List[str]):
    """Call after renaming a category."""
    if parent_path:
        path_str = " > ".join(parent_path)
        sync_codex_tree(f"Rename category '{old_name}' -> '{new_name}' under {path_str}")
    else:
        sync_codex_tree(f"Rename root category '{old_name}' -> '{new_name}'")
