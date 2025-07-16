"""
Dependency injection for FastAPI
"""

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.vector_store import VectorStoreService

# Security
security = HTTPBearer(auto_error=False)


async def get_vector_service() -> VectorStoreService:
    """Get vector store service dependency"""
    from app.main import app
    if not hasattr(app.state, 'vector_service'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store service not available"
        )
    return app.state.vector_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Get current user from JWT token (placeholder for future authentication)
    """
    # For now, return anonymous user
    # In the future, implement JWT token validation
    return "anonymous"


def get_rate_limiter():
    """
    Rate limiter dependency (placeholder for future implementation)
    """
    # Placeholder for rate limiting logic
    # Could use Redis or in-memory store
    pass
