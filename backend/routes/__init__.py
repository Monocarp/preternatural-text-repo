# backend/routes/__init__.py
"""
Route modules for the Lexicon of the Unexplained API.

This package contains FastAPI APIRouter instances for each domain:
- search: Story search endpoints
- tree: Codex tree and category management
- stories: Story CRUD and rendering
- books: Book listing and full text
- admin: Database migrations, reloading, cleanup
"""

from .search import router as search_router
from .tree import router as tree_router
from .stories import router as stories_router
from .books import router as books_router
from .admin import router as admin_router

__all__ = [
    "search_router",
    "tree_router",
    "stories_router",
    "books_router",
    "admin_router",
]
