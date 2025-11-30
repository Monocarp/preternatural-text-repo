# backend/routes/errors.py
"""
Standardized error handling for the Lexicon API.

Provides:
- AppError: Custom exception with error codes
- ErrorCode: Enum of all application error codes
- error_response: Helper to build consistent error responses
- exception_handlers: FastAPI exception handlers
"""

from enum import Enum
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

log = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Application error codes for programmatic error handling."""
    
    # Authentication (1xxx)
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_NOT_CONFIGURED = "AUTH_NOT_CONFIGURED"
    
    # Authorization (2xxx)
    FORBIDDEN_EDITOR_REQUIRED = "FORBIDDEN_EDITOR_REQUIRED"
    FORBIDDEN_INSUFFICIENT_PERMISSIONS = "FORBIDDEN_INSUFFICIENT_PERMISSIONS"
    
    # Resource Not Found (3xxx)
    NOT_FOUND_STORY = "NOT_FOUND_STORY"
    NOT_FOUND_BOOK = "NOT_FOUND_BOOK"
    NOT_FOUND_CATEGORY = "NOT_FOUND_CATEGORY"
    NOT_FOUND_FILE = "NOT_FOUND_FILE"
    
    # Validation (4xxx)
    VALIDATION_INVALID_INPUT = "VALIDATION_INVALID_INPUT"
    VALIDATION_DUPLICATE_TITLE = "VALIDATION_DUPLICATE_TITLE"
    VALIDATION_OVERLAP_DETECTED = "VALIDATION_OVERLAP_DETECTED"
    VALIDATION_OUT_OF_BOUNDS = "VALIDATION_OUT_OF_BOUNDS"
    VALIDATION_CONTENT_TOO_SHORT = "VALIDATION_CONTENT_TOO_SHORT"
    
    # Operation Failed (5xxx)
    OPERATION_FAILED = "OPERATION_FAILED"
    OPERATION_EXPORT_FAILED = "OPERATION_EXPORT_FAILED"
    OPERATION_SEARCH_FAILED = "OPERATION_SEARCH_FAILED"
    OPERATION_UPDATE_FAILED = "OPERATION_UPDATE_FAILED"
    OPERATION_DELETE_FAILED = "OPERATION_DELETE_FAILED"
    OPERATION_INDEX_FAILED = "OPERATION_INDEX_FAILED"
    
    # Server Errors (6xxx)
    SERVER_DATABASE_ERROR = "SERVER_DATABASE_ERROR"
    SERVER_INTERNAL_ERROR = "SERVER_INTERNAL_ERROR"
    SERVER_MIGRATION_FAILED = "SERVER_MIGRATION_FAILED"


# Map error codes to HTTP status codes
ERROR_STATUS_MAP: Dict[ErrorCode, int] = {
    # 401 Unauthorized
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_NOT_CONFIGURED: 500,
    
    # 403 Forbidden
    ErrorCode.FORBIDDEN_EDITOR_REQUIRED: 403,
    ErrorCode.FORBIDDEN_INSUFFICIENT_PERMISSIONS: 403,
    
    # 404 Not Found
    ErrorCode.NOT_FOUND_STORY: 404,
    ErrorCode.NOT_FOUND_BOOK: 404,
    ErrorCode.NOT_FOUND_CATEGORY: 404,
    ErrorCode.NOT_FOUND_FILE: 404,
    
    # 400 Bad Request
    ErrorCode.VALIDATION_INVALID_INPUT: 400,
    ErrorCode.VALIDATION_DUPLICATE_TITLE: 400,
    ErrorCode.VALIDATION_OVERLAP_DETECTED: 400,
    ErrorCode.VALIDATION_OUT_OF_BOUNDS: 400,
    ErrorCode.VALIDATION_CONTENT_TOO_SHORT: 400,
    
    # 500 Internal Server Error
    ErrorCode.OPERATION_FAILED: 500,
    ErrorCode.OPERATION_EXPORT_FAILED: 500,
    ErrorCode.OPERATION_SEARCH_FAILED: 500,
    ErrorCode.OPERATION_UPDATE_FAILED: 500,
    ErrorCode.OPERATION_DELETE_FAILED: 500,
    ErrorCode.OPERATION_INDEX_FAILED: 500,
    ErrorCode.SERVER_DATABASE_ERROR: 500,
    ErrorCode.SERVER_INTERNAL_ERROR: 500,
    ErrorCode.SERVER_MIGRATION_FAILED: 500,
}


class ErrorResponse(BaseModel):
    """Standardized error response schema."""
    error: str  # Error code enum value
    message: str  # Human-readable message
    detail: Optional[str] = None  # Technical details (dev mode only)
    context: Optional[Dict[str, Any]] = None  # Additional context


class AppError(HTTPException):
    """
    Application-specific exception with error codes.
    
    Usage:
        raise AppError(ErrorCode.NOT_FOUND_STORY, "Story not found", detail="Title: foo")
        raise AppError(ErrorCode.VALIDATION_DUPLICATE_TITLE, f"Story '{title}' already exists")
    """
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.detail_msg = detail
        self.context = context
        status_code = ERROR_STATUS_MAP.get(code, 500)
        super().__init__(status_code=status_code, detail=message)


def error_response(
    code: ErrorCode,
    message: str,
    detail: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    include_detail: bool = False
) -> JSONResponse:
    """
    Build a standardized JSON error response.
    
    Args:
        code: Error code enum value
        message: Human-readable error message
        detail: Technical details (included only if include_detail=True)
        context: Additional context data
        include_detail: Whether to include technical details in response
    
    Returns:
        JSONResponse with consistent error format
    """
    status_code = ERROR_STATUS_MAP.get(code, 500)
    
    body = {
        "error": code.value,
        "message": message
    }
    
    if include_detail and detail:
        body["detail"] = detail
    
    if context:
        body["context"] = context
    
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    FastAPI exception handler for AppError.
    
    Register with:
        app.add_exception_handler(AppError, app_error_handler)
    """
    log.warning(f"AppError: {exc.code.value} - {exc.message}")
    if exc.detail_msg:
        log.debug(f"  Detail: {exc.detail_msg}")
    
    body = {
        "error": exc.code.value,
        "message": exc.message
    }
    
    # Include detail in non-production
    import os
    if os.getenv("ENVIRONMENT", "development") != "production" and exc.detail_msg:
        body["detail"] = exc.detail_msg
    
    if exc.context:
        body["context"] = exc.context
    
    return JSONResponse(status_code=exc.status_code, content=body)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unhandled exceptions.
    
    Register with:
        app.add_exception_handler(Exception, generic_exception_handler)
    """
    log.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
    
    import os
    is_dev = os.getenv("ENVIRONMENT", "development") != "production"
    
    body = {
        "error": ErrorCode.SERVER_INTERNAL_ERROR.value,
        "message": "An unexpected error occurred"
    }
    
    if is_dev:
        body["detail"] = f"{type(exc).__name__}: {str(exc)}"
    
    return JSONResponse(status_code=500, content=body)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handler for standard HTTPException to ensure consistent format.
    
    Register with:
        app.add_exception_handler(HTTPException, http_exception_handler)
    """
    # Map common HTTP status codes to error codes
    status_to_code = {
        400: ErrorCode.VALIDATION_INVALID_INPUT,
        401: ErrorCode.AUTH_REQUIRED,
        403: ErrorCode.FORBIDDEN_INSUFFICIENT_PERMISSIONS,
        404: ErrorCode.NOT_FOUND_STORY,  # Generic not found
        500: ErrorCode.SERVER_INTERNAL_ERROR,
    }
    
    code = status_to_code.get(exc.status_code, ErrorCode.SERVER_INTERNAL_ERROR)
    
    body = {
        "error": code.value,
        "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    }
    
    return JSONResponse(status_code=exc.status_code, content=body)
