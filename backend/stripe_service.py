"""Stripe service: Checkout sessions for Pro subscription and credit packs."""
from __future__ import annotations

import os
import logging
from typing import Literal

import stripe
from fastapi import HTTPException

log = logging.getLogger("stripe_service")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Hard-coded prices (CAD cents) — in real life put these as Stripe price IDs.
PRO_PRICE_CAD_CENTS = 1200  # 12$ / month
CREDIT_PACKS = {
    "5": {"credits": 5, "amount_cad_cents": 399, "label": "5 crédits"},
    "15": {"credits": 15, "amount_cad_cents": 999, "label": "15 crédits"},
    "40": {"credits": 40, "amount_cad_cents": 1999, "label": "40 crédits"},
}


def _build_success_cancel(view: str):
    success_url = f"{FRONTEND_URL}/{view}?status=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{FRONTEND_URL}/{view}?status=cancel"
    return success_url, cancel_url


def create_subscription_session(user_id: str, user_email: str) -> str:
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe non configuré.")
    success_url, cancel_url = _build_success_cancel("credits")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user_email,
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "recurring": {"interval": "month"},
                    "product_data": {"name": "ManuelIA Pro"},
                    "unit_amount": PRO_PRICE_CAD_CENTS,
                },
                "quantity": 1,
            }],
            metadata={"user_id": user_id, "kind": "subscription"},
            allow_promotion_codes=True,
        )
        return session.url
    except Exception as e:
        log.error("stripe sub session failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe a échoué: {e}")


def create_credits_session(user_id: str, user_email: str, pack: Literal["5", "15", "40"]) -> str:
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe non configuré.")
    if pack not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Pack inconnu.")
    p = CREDIT_PACKS[pack]
    success_url, cancel_url = _build_success_cancel("credits")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user_email,
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "product_data": {"name": f"ManuelIA — {p['label']}"},
                    "unit_amount": p["amount_cad_cents"],
                },
                "quantity": 1,
            }],
            metadata={
                "user_id": user_id,
                "kind": "credits",
                "credits": str(p["credits"]),
                "pack": pack,
            },
        )
        return session.url
    except Exception as e:
        log.error("stripe credits session failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe a échoué: {e}")


def verify_webhook(payload: bytes, sig_header: str):
    if not WEBHOOK_SECRET:
        # No secret configured — parse but don't verify signature.
        log.warning("[STRIPE WEBHOOK] STRIPE_WEBHOOK_SECRET not set, accepting without verification.")
        try:
            return stripe.Event.construct_from(
                __import__("json").loads(payload.decode("utf-8")), stripe.api_key
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Webhook payload illisible: {e}")
    try:
        return stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook signature invalide: {e}")
