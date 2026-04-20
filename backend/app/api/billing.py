"""Billing and Stripe integration routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import get_current_user_id
from app.models.models import Event, EventTier, EventTierName, Payment, PaymentStatus, User
from app.schemas.schemas import CheckoutRequest, TierResponse

router = APIRouter()


@router.get("/tiers", response_model=dict)
async def list_tiers(db: AsyncSession = Depends(get_db)):
    """List available event pricing tiers."""
    result = await db.execute(select(EventTier).order_by(EventTier.price_cents))
    tiers = result.scalars().all()
    return {"data": [TierResponse.model_validate(t) for t in tiers]}


@router.post("/checkout", response_model=dict)
async def create_checkout_session(
    body: CheckoutRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe checkout session for an event tier."""
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY:
        raise AppError(503, "BILLING_UNAVAILABLE", "Billing is not configured")

    # Verify event ownership
    result = await db.execute(
        select(Event).where(Event.id == body.event_id, Event.deleted_at.is_(None))
    )
    event = result.scalar_one_or_none()
    if not event or event.user_id != user_id:
        raise AppError(404, "EVENT_NOT_FOUND", "Event not found")

    # Get tier price
    result = await db.execute(
        select(EventTier).where(EventTier.name == EventTierName(body.tier.value))
    )
    tier = result.scalar_one_or_none()
    if not tier or tier.price_cents == 0:
        raise AppError(400, "INVALID_TIER", "Cannot checkout a free tier")

    # Get user for stripe customer id
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    session_kwargs: dict = {
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": tier.price_cents,
                    "product_data": {
                        "name": f"EventVault {tier.name.value.capitalize()} — {event.name}",
                    },
                },
                "quantity": 1,
            }
        ],
        "success_url": f"{settings.BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.BASE_URL}/billing/cancel",
        "metadata": {
            "event_id": str(event.id),
            "user_id": str(user_id),
            "tier": body.tier.value,
        },
    }

    if user and user.stripe_customer_id:
        session_kwargs["customer"] = user.stripe_customer_id

    session = stripe.checkout.Session.create(**session_kwargs)
    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events."""
    settings = get_settings()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise AppError(503, "BILLING_UNAVAILABLE", "Webhook is not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise AppError(400, "INVALID_SIGNATURE", "Webhook signature verification failed")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata", {})
        event_id = meta.get("event_id")
        user_id_str = meta.get("user_id")
        tier = meta.get("tier")

        if event_id and user_id_str and tier:
            app_event_result = await db.execute(
                select(Event).where(Event.id == UUID(event_id))
            )
            app_event = app_event_result.scalar_one_or_none()

            if app_event:
                app_event.tier = EventTierName(tier)

                # Update tier limits from EventTier table
                tier_result = await db.execute(
                    select(EventTier).where(EventTier.name == EventTierName(tier))
                )
                tier_obj = tier_result.scalar_one_or_none()
                if tier_obj:
                    app_event.upload_limit_mb = tier_obj.max_file_size_mb
                    app_event.total_storage_limit_gb = tier_obj.max_total_storage_gb

                # Record payment
                payment = Payment(
                    user_id=UUID(user_id_str),
                    event_id=UUID(event_id),
                    stripe_payment_intent_id=session.get("payment_intent", session["id"]),
                    amount_cents=session.get("amount_total", 0),
                    status=PaymentStatus.SUCCEEDED,
                    description=f"EventVault {tier.capitalize()} tier",
                )
                db.add(payment)
                await db.flush()

    return {"received": True}


@router.get("/payments", response_model=dict)
async def list_payments(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List payment history for the authenticated user."""
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    return {
        "data": [
            {
                "id": str(p.id),
                "event_id": str(p.event_id) if p.event_id else None,
                "amount_cents": p.amount_cents,
                "currency": p.currency,
                "status": p.status.value,
                "description": p.description,
                "created_at": p.created_at.isoformat(),
            }
            for p in payments
        ]
    }
