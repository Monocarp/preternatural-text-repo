# backend/storage/pending.py
"""
Pending stories queue management.

Handles the queue of stories awaiting processing:
- Loading/saving the pending queue
- Checking for overlapping story boundaries
"""

import os
import json
import logging

from state import app_state
from .books import load_story_positions

logger = logging.getLogger(__name__)


def load_pending_stories() -> list[dict]:
    """
    Load the pending stories queue from disk.
    
    Returns:
        List of pending story dictionaries
    """
    if not os.path.exists(app_state.pending_stories_path):
        return []
    
    with open(app_state.pending_stories_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_pending_stories(pending_stories: list[dict]) -> None:
    """
    Save the pending stories queue to disk.
    
    Args:
        pending_stories: List of pending story dictionaries
    """
    with open(app_state.pending_stories_path, "w", encoding="utf-8") as f:
        json.dump(pending_stories, f, indent=2)


def check_story_overlap(
    book_slug: str,
    new_start: int,
    new_end: int,
    exclude_title: str = None
) -> tuple[bool, list[dict]]:
    """
    Check if a new story's character range overlaps with existing stories.
    
    Args:
        book_slug: The book to check
        new_start: Start character position of the new story
        new_end: End character position of the new story
        exclude_title: Optional title to exclude from overlap check (for editing)
    
    Returns:
        Tuple of (has_overlap: bool, overlaps: list of overlapping stories)
        
        Each overlap dict contains:
        - title: Story title
        - start_char: Existing story start
        - end_char: Existing story end
        - overlap_type: "partial" or "full"
        - overlap_chars: Number of overlapping characters
        - overlap_percent: Percentage of new story that overlaps
    """
    positions = load_story_positions(book_slug)
    if not positions:
        return False, []
    
    new_length = new_end - new_start
    overlaps = []
    
    for title, bounds in positions.items():
        if exclude_title and title == exclude_title:
            continue
        
        existing_start = bounds.get("start_char", 0)
        existing_end = bounds.get("end_char", 0)
        
        # Check for overlap: ranges overlap if one starts before the other ends
        if new_start < existing_end and new_end > existing_start:
            # Calculate overlap amount
            overlap_start = max(new_start, existing_start)
            overlap_end = min(new_end, existing_end)
            overlap_chars = overlap_end - overlap_start
            overlap_percent = round((overlap_chars / new_length) * 100) if new_length > 0 else 0
            
            overlaps.append({
                "title": title,
                "start_char": existing_start,
                "end_char": existing_end,
                "overlap_type": "partial" if (new_start > existing_start or new_end < existing_end) else "full",
                "overlap_chars": overlap_chars,
                "overlap_percent": overlap_percent
            })
    
    return bool(overlaps), overlaps
