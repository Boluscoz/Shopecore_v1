import hashlib
import hmac
import json
import os
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.catalog.models import Product
from apps.orders.models import Order, Payment
from apps.orders import services as order_services
from djpaystack import PaystackClient


class PaymentError(Exception):
    """Raised for payment/provider failures."""


class CurrencyError(PaymentError):
    """Raised when the provider currency does not match the order."""


# ---------------------------------------------------------------------------
# Provider abstraction (Paystack). All real SDK calls go through these stubs
# so the business logic below never references a provider directly.
# ---------------------------------------------------------------------------

def _paystack_secret():
    return getattr(settings, "PAYSTACK", {}).get("SECRET_KEY") or os.environ.get('Pk_secret_KEY')


def _paystack_base_url():
    return getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")


def _paystack_client():
    return PaystackClient()


def initialize_provider(amount, currency, customer_email, metadata=None):
    """Create a Paystack transaction and return its reference.

    Expected return:
      {"reference": "ref_...", "access_code": "...", "amount": <kobo int>}
    """
    client = _paystack_client()
    response = client.transactions.initialize(
        email=customer_email,
        amount=amount,
        currency=currency,
        metadata=metadata,
    )
    data = response.get("data", {})
    return {
        "reference": data.get("reference"),
        "access_code": data.get("access_code"),
        "amount": data.get("amount"),
    }


def provider_verify_reference(reference):
    """Fetch the transaction from Paystack by reference.

    Expected return: the decoded JSON body,
    e.g. {"status": True, "data": {"reference":..., "amount":..., "currency":
    "NGN", "status": "success", ...}}.
    """
    client = _paystack_client()
    return client.transactions.verify(reference=reference)


def verify_webhook_signature(payload, signature):
    """Verify a Paystack webhook signature using HMAC-SHA512."""
    secret = _paystack_secret()
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Payment state machine (distinct from order state)
# ---------------------------------------------------------------------------

@transaction.atomic
def initialize(order_id, currency="NGN", metadata=None):
    """Initialize a payment for an order: create the Payment row and return it.

    Order state stays 'pending'; only the Payment row is created here.
    """
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise PaymentError("Order not found.")

    amount = order.total
    customer_email = (metadata or {}).get("customer_email", "")

    provider_payload = initialize_provider(
        amount=int(amount * 100),
        currency=currency,
        customer_email=customer_email,
        metadata=metadata,
    )

    payment = Payment.objects.create(
        order=order,
        provider="paystack",
        currency=currency,
        customer_email=customer_email,
        amount=amount,
        status="pending",
        external_id=provider_payload["reference"],
        metadata={
            **(metadata or {}),
            "access_code": provider_payload.get("access_code"),
            "provider_amount": provider_payload.get("amount"),
        },
    )
    return payment


def customer_status(external_id):
    """Look up a customer's payment status by provider reference.

    Verifies amount/currency/final status server-side before returning.
    """
    try:
        payment = Payment.objects.get(external_id=external_id)
    except Payment.DoesNotExist:
        raise PaymentError("Payment not found.")

    provider_data = provider_verify_reference(external_id)
    _assert_provider_matches(payment, provider_data)

    return {
        "payment": payment,
        "provider_status": provider_data.get("data", {}).get("status"),
        "verified": provider_data.get("data", {}).get("status") == "success",
    }


def _assert_provider_matches(payment, provider_data):
    """Server-side re-verification of amount, currency and final status."""
    data = provider_data.get("data")
    if not data:
        raise PaymentError("Provider returned no data.")

    expected_amount = int(payment.amount * 100)
    if int(data.get("amount", -1)) != expected_amount:
        raise PaymentError("Amount mismatch with provider.")
    if data.get("currency") != payment.currency:
        raise CurrencyError("Currency mismatch with provider.")

    final_status = data.get("status")
    if final_status not in ("success", "failed", "abandoned", "expired"):
        raise PaymentError("Unknown provider status.")


@transaction.atomic
def verify_provider_reference(order_id, external_id, provider="paystack"):
    """Confirm a payment authorization and allocate stock.

    Server-side re-checks amount, currency and final status against the
    provider before touching anything. Then delegates stock allocation to
    the orders service.
    """
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise PaymentError("Order not found.")

    try:
        payment = Payment.objects.select_for_update().get(
            order=order, external_id=external_id, provider=provider
        )
    except Payment.DoesNotExist:
        raise PaymentError("Payment not found.")

    if payment.status == "captured":
        return order, payment, "already_captured"

    provider_data = provider_verify_reference(external_id)
    _assert_provider_matches(payment, provider_data)

    final_status = provider_data["data"].get("status")
    if final_status != "success":
        payment.status = "failed"
        payment.metadata = {**payment.metadata, "provider_data": provider_data}
        payment.save()
        order_services.apply_payment_result(order.id, "failed")
        return order, payment, "failed"

    # Re-check stock under row locks so concurrent captures cannot oversell.
    # OrderItem stores a snapshot (product_name), not a FK, so we match by
    # name to find the live Product row for stock checks.
    insufficient = []
    for item in order.items.all():
        product = (
            Product.objects.select_for_update()
            .filter(name=item.product_name, is_active=True)
            .first()
        )
        if product is None:
            insufficient.append(
                {"product_name": item.product_name, "reason": "unavailable"}
            )
            continue
        if product.stock < item.quantity:
            insufficient.append(
                {
                    "product_name": product.name,
                    "reason": "insufficient_stock",
                    "available": product.stock,
                    "requested": item.quantity,
                }
            )

    if insufficient:
        payment.status = "failed"
        payment.metadata = {
            **payment.metadata,
            "provider_data": provider_data,
            "insufficient": insufficient,
        }
        payment.save()
        order_services.apply_payment_result(
            order.id, "stock_out", insufficient)
        return order, payment, "stock_out"

    # Allocate stock and capture the payment.
    for item in order.items.all():
        product = Product.objects.select_for_update().get(
            name=item.product_name, is_active=True
        )
        product.stock = max(0, product.stock - item.quantity)
        product.save()

    payment.status = "captured"
    payment.metadata = {**payment.metadata, "provider_data": provider_data}
    payment.save()
    order_services.apply_payment_result(order.id, "captured")
    return order, payment, "captured"


@transaction.atomic
def handle_webhook(payload, signature):
    """Process a Paystack webhook. Signature-verified before any state change."""
    if not verify_webhook_signature(payload, signature):
        raise PaymentError("Invalid webhook signature.")

    event = json.loads(payload)
    event_type = event.get("event")
    data = event.get("data", {})
    reference = data.get("reference")

    if not reference:
        raise PaymentError("Webhook missing reference.")

    try:
        payment = Payment.objects.select_for_update().get(external_id=reference)
    except Payment.DoesNotExist:
        return {"event": event_type, "reference": reference, "action": "ignored"}

    if event_type == "charge.success":
        payment.status = "captured"
        payment.metadata = {**payment.metadata, "webhook": event}
        payment.save()
        order_services.apply_payment_result(payment.order_id, "captured")
        return {"event": event_type, "reference": reference, "action": "captured"}

    if event_type == "charge.failed":
        payment.status = "failed"
        payment.metadata = {**payment.metadata, "webhook": event}
        payment.save()
        order_services.apply_payment_result(payment.order_id, "failed")
        return {"event": event_type, "reference": reference, "action": "failed"}

    return {"event": event_type, "reference": reference, "action": "unhandled"}


@transaction.atomic
def refund(order_id, amount=None, reason=""):
    """Refund a captured payment. Provider call is stubbed."""
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise PaymentError("Order not found.")

    payment = (
        Payment.objects.select_for_update()
        .filter(order=order, status="captured")
        .first()
    )
    if payment is None:
        raise PaymentError("No captured payment to refund.")

    refund_amount = amount if amount is not None else str(payment.amount)
    # Provider refund call.
    client = _paystack_client()
    client.refunds.create(
        transaction=payment.external_id,
        amount=int(float(refund_amount) * 100),
        customer_note=reason,
    )
