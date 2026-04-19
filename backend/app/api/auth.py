"""Auth routes — registration, login, token refresh."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.post("/register")
async def register(db: AsyncSession = Depends(get_db)):
    """Register a new host account."""
    # TODO: Implement
    return {"message": "register endpoint"}


@router.post("/login")
async def login(db: AsyncSession = Depends(get_db)):
    """Login and receive JWT tokens."""
    # TODO: Implement
    return {"message": "login endpoint"}


@router.post("/refresh")
async def refresh_token():
    """Refresh an access token."""
    # TODO: Implement
    return {"message": "refresh endpoint"}
