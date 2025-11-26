import logging
import re
import os

# Import state for centralized globals
from state import app_state

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
def _get_load_full_md():
    from utils_legacy import load_full_md
    return load_full_md

def _get_load_story_positions():
    from utils_legacy import load_story_positions
    return load_story_positions

# Get list of books from state
books = app_state.books

def render_md_with_scroll_and_highlight(book_slug, start_char, end_char, page, search_query=None):
    load_full_md = _get_load_full_md()
    full_md = load_full_md(book_slug)
    try:
        logger.debug(f"Rendering MD for {book_slug} with start_char={start_char}, end_char={end_char}, page={page}")
        # Step 1: Adjust for HTML escaping (< and >)
        escape_pattern = r'[<>]'
        escape_matches = list(re.finditer(escape_pattern, full_md))
        def get_escape_delta(pos):
            delta = 0
            for m in escape_matches:
                if m.start() < pos:
                    delta += 3 # < or > adds 3 characters
            return delta
        escaped_start = start_char + get_escape_delta(start_char)
        escaped_end = end_char + get_escape_delta(end_char)
        # Escape the MD
        escaped_md = full_md.replace('<', '&lt;').replace('>', '&gt;')
        # Step 2: Adjust for anchor insertions on escaped_md
        anchor_pattern = r'\\?\[\s*Page\s*(\d+)\s*\\?\]'
        anchor_matches = list(re.finditer(anchor_pattern, escaped_md, re.IGNORECASE))
        def get_anchor_delta(pos):
            delta = 0
            for m in anchor_matches:
                if m.start() < pos:
                    page_num = m.group(1)
                    replacement = f'<div id="page-{page_num}">[Page {page_num}]</div>'
                    orig_len = m.end() - m.start()
                    rep_len = len(replacement)
                    delta += rep_len - orig_len
            return delta
        adjusted_start = escaped_start + get_anchor_delta(escaped_start)
        adjusted_end = escaped_end + get_anchor_delta(escaped_end)
        # Add anchors
        def replace_anchor(match):
            page_num = match.group(1)
            return f'<div id="page-{page_num}">[Page {page_num}]</div>'
        md_with_anchors = re.sub(anchor_pattern, replace_anchor, escaped_md, flags=re.IGNORECASE)
        # Step 3: If search_query (from Exact mode), add red highlights and adjust deltas
        md_with_red = md_with_anchors
        if search_query:
            search_query = search_query.strip()
            if ' ' in search_query:
                pattern = re.escape(search_query)
            else:
                pattern = r'\b' + re.escape(search_query) + r'\b'
            red_matches = list(re.finditer(pattern, md_with_anchors, re.IGNORECASE))
            def get_red_delta(pos):
                delta = 0
                for m in red_matches:
                    if m.start() < pos:
                        delta += 33 # len('<span style="color: red;"></span>')
                return delta
            adjusted_start += get_red_delta(adjusted_start)
            adjusted_end += get_red_delta(adjusted_end)
            # Apply red highlights
            def replace_red(match):
                return '<span style="color: red;">' + match.group(0) + '</span>'
            md_with_red = re.sub(pattern, replace_red, md_with_anchors, flags=re.IGNORECASE)
        # Highlight story range using adjusted positions with ID for scrolling
        highlighted = (
            md_with_red[:adjusted_start] +
            '<span id="story-highlight" style="background-color: #fbbf24; color: #111827; padding: 2px 4px; border-radius: 3px;">' +
            md_with_red[adjusted_start:adjusted_end] +
            '</span>' +
            md_with_red[adjusted_end:]
        )
        html = f"""
        <div id="book-context-container" style="height: 500px; overflow-y: scroll; font-family: Arial; white-space: pre-wrap; background-color: #1f2937; color: #f3f4f6; padding: 1rem; border-radius: 0.5rem;">{highlighted}</div>
        """
        return html
    except Exception as e:
        logger.error(f"Failed to render MD for {book_slug}: {e}")
        return "Error rendering story."

def render_static_story(story):
    """Render a static story from markdown"""
    load_full_md = _get_load_full_md()
    book_slug = story['book_slug']
    full_md = load_full_md(book_slug)
    text = full_md[story['start_char']:story['end_char']]
    return text # Frontend already displays metadata in header, so just return the story text

def find_book_slug(title):
    load_story_positions = _get_load_story_positions()
    # Refresh books list from state in case it was populated after module load
    current_books = app_state.books if app_state.books else books
    for book_slug in current_books:
        positions = load_story_positions(book_slug)
        if title in positions:
            return book_slug
    raise ValueError(f"Book not found for title: {title}")