"""Billing and Stripe integration routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

router = APIRouter()


@router.get("/tiers")
async def list_tiers(db: AsyncSession = Depends(get_db)):
    """List available event pricing tiers."""
    # TODO: Implement — return from EventTier table
    return {"data": []}


@router.post("/checkout")
async def create_checkout_session(
    user_id=Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe checkout session for an event tier."""
    # TODO: Implement — stripe.checkout.Session.create(...)
    return {"message": "checkout endpoint"}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events (payment confirmation, etc.)."""
    # TODO: Implement — verify signature, handle checkout.session.completed
    return {"received": True}


@router.get("/payments")
async def list_payments(
    user_id=Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List payment history for the authenticated user."""
    # TODO: Implement
    return {"data": []}
