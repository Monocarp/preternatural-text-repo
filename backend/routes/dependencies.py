# backend/routes/dependencies.py
"""
Shared dependencies for route modules.

Contains authentication helpers, Pydantic models, and common imports
that are used across multiple route files.
"""

import os
import logging
import urllib.parse
import json
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt
from jwt import PyJWKClient
import requests

from models import SessionLocal, User
from .errors import AppError, ErrorCode

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Paths
# ------------------------------------------------------------------ #
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOKS_DIR = os.path.join(ROOT, "books")
DATA_DIR = os.path.join(ROOT, "data")

# ------------------------------------------------------------------ #
# Auth Configuration
# ------------------------------------------------------------------ #
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() == "true"
security = HTTPBearer(auto_error=False)

STACK_PROJECT_ID = os.getenv("STACK_PROJECT_ID") or os.getenv("VITE_STACK_PROJECT_ID") or os.getenv("NEXT_PUBLIC_STACK_PROJECT_ID")
STACK_JWKS_URL = os.getenv("STACK_JWKS_URL")
SECRET_SERVER_KEY = os.getenv("STACK_SECRET_SERVER_KEY")
EDITOR_EMAILS = {e.strip().lower() for e in os.getenv("EDITOR_EMAILS", "").split(",") if e.strip()}

JWKS_URL = None
jwks_client = None

if STACK_JWKS_URL:
    JWKS_URL = STACK_JWKS_URL
elif STACK_PROJECT_ID:
    JWKS_URL = f"https://api.stack-auth.com/api/v1/projects/{STACK_PROJECT_ID}/.well-known/jwks.json"

if JWKS_URL:
    try:
        jwks_client = PyJWKClient(JWKS_URL)
        log.info(f"Initialized JWKS client with URL: {JWKS_URL}")
    except Exception as e:
        log.error(f"Failed to initialize JWKS client: {e}")

# ------------------------------------------------------------------ #
# Auth Dependencies
# ------------------------------------------------------------------ #
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Extract and validate JWT token from request.
    
    Checks Authorization header first, then Stack Auth cookies.
    Returns decoded JWT payload on success.
    
    Raises:
        HTTPException 401: If no valid token found
        HTTPException 500: If JWT verification not configured
    """
    if DISABLE_AUTH:
        return {"sub": "dev-user"}
    
    token = None
    if credentials:
        token = credentials.credentials
    
    if not token:
        # Check Stack Auth cookie
        stack_access_raw = request.cookies.get('stack-access')
        if stack_access_raw:
            try:
                decoded = urllib.parse.unquote(stack_access_raw)
                parsed = json.loads(decoded)
                if isinstance(parsed, list) and len(parsed) >= 2 and isinstance(parsed[1], str):
                    token = parsed[1]
            except Exception as e:
                log.warning(f"Failed to parse 'stack-access' cookie: {e}")

        if not token:
            token = request.cookies.get('stack-access-token') or \
                   request.cookies.get('stack_token') or \
                   request.cookies.get('__session') or \
                   request.cookies.get('session') or \
                   (request.cookies.get(f'stack-{STACK_PROJECT_ID}-access-token') if STACK_PROJECT_ID else None)

        # Fallback: scan for JWT-looking cookie
        if not token and request.cookies:
            for cookie_name, cookie_val in request.cookies.items():
                if isinstance(cookie_val, str) and cookie_val.count('.') == 2 and len(cookie_val) > 100:
                    token = cookie_val
                    break
    
    if not token:
        raise AppError(ErrorCode.AUTH_REQUIRED, "Authentication required")
    
    if not jwks_client:
        raise AppError(ErrorCode.AUTH_NOT_CONFIGURED, "JWT verification not configured", detail="Set STACK_PROJECT_ID in environment")
    
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=SECRET_SERVER_KEY if SECRET_SERVER_KEY else None,
                options={"verify_exp": True, "verify_aud": bool(SECRET_SERVER_KEY)}
            )
        except jwt.InvalidAudienceError:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_exp": True, "verify_aud": False}
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppError(ErrorCode.AUTH_TOKEN_EXPIRED, "Token has expired")
    except Exception as e:
        log.error(f"JWT verification failed: {str(e)}")
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "Invalid token", detail=str(e))


async def require_editor(user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Verify user has editor role.
    
    Auto-provisions new users as 'viewer'.
    Auto-promotes users in EDITOR_EMAILS to 'editor'.
    
    Raises:
        HTTPException 403: If user is not an editor
    """
    if DISABLE_AUTH:
        return user
    
    session = SessionLocal()
    try:
        sub = user.get("sub")
        email = (user.get("email") or "").lower()
        name = user.get("name") or ""

        db_user = session.query(User).filter_by(id=sub).first()

        if not db_user:
            db_user = User(id=sub, name=name, email=email, role="viewer")
            session.add(db_user)
            session.commit()
            log.info(f"Auto-provisioned user {email or sub} with role 'viewer'")

        if email and email in EDITOR_EMAILS and db_user.role != "editor":
            db_user.role = "editor"
            session.commit()
            log.info(f"Auto-promoted {email} to 'editor' via EDITOR_EMAILS")

        if not db_user or db_user.role != "editor":
            raise AppError(ErrorCode.FORBIDDEN_EDITOR_REQUIRED, "Editor role required")
        return user
    finally:
        session.close()


# ------------------------------------------------------------------ #
# Pydantic Models (Request/Response Schemas)
# ------------------------------------------------------------------ #
class SearchQuery(BaseModel):
    """Search request body."""
    query: str
    source_filter: Optional[str] = "All Sources"
    type_filter: Optional[str] = "Both"
    search_mode: Optional[str] = "Both"
    top_k: int = Field(1000, ge=1, le=5000)
    min_score: float = Field(0.1, ge=0.0, le=1.0)
    assignment_filter: Optional[str] = "all"


class AssignBody(BaseModel):
    """Category assignment request."""
    path: List[str]  # e.g. ["Demonic Activity", "Obsession", "Fear/Anxiety"]
    story: Dict[str, Any]


class RemoveBody(BaseModel):
    """Category removal request."""
    path: List[str]
    title: str


class RenderQuery(BaseModel):
    """Story render request."""
    title: str
    mode: str = Field("static", pattern="^(static|book)$")
    search_query: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class UpdateBoundariesBody(BaseModel):
    """Update story boundaries request."""
    title: str
    book_slug: str
    start_char: int
    end_char: int


class UpdateTitleBody(BaseModel):
    """Update story title request."""
    old_title: str
    new_title: str
    book_slug: str


class UpdateKeywordsBody(BaseModel):
    """Update story keywords request."""
    title: str
    book_slug: str
    keywords: str


class AddStoryBody(BaseModel):
    """Add new story request."""
    book_slug: str
    title: str
    start_char: int
    end_char: int
    pages: str
    keywords: str = ""
    force_overlap: bool = False


class ExportBody(BaseModel):
    """Export stories request."""
    stories: List[Dict[str, Any]]
    format: str = Field("md", pattern="^(md|pdf|word)$")
    is_single: bool = True


class BookResponse(BaseModel):
    """Book response model."""
    id: int
    slug: str
    title: str
    author: Optional[str]
    year: Optional[str]
    story_count: Optional[int] = 0

    class Config:
        from_attributes = True
