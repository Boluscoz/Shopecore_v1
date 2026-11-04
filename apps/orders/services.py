from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.catalog.models import Product
from .models import Order, OrderItem, Payment


class CheckoutError(Exception):
    """Raised for user-facing checkout/validation failures."""


def _validate_items(items_data):
    """Validate the requested items and return normalized rows.

    Each row is a dict with keys: product, unit_price, quantity.
    Raises CheckoutError on any validation failure.
    """
    if not items_data:
        raise CheckoutError("No items provided.")

    rows = []
    for entry in items_data:
        product_id = entry.get("product_id") or entry.get("product")
        try:
            quantity = int(entry.get("quantity", 1))
        except (TypeError, ValueError):
            raise CheckoutError("Invalid quantity.")
        if quantity <= 0:
            raise CheckoutError("Quantity must be greater than zero.")

        try:
            product = Product.objects.get(pk=product_id)
        except (Product.DoesNotExist, ValueError, TypeError):
            raise CheckoutError("Product not found.")
        if not product.is_active:
            raise CheckoutError("Product is inactive.")

        rows.append(
            {
                "product": product,
                "unit_price": Decimal(str(product.price)),
                "quantity": quantity,
            }
        )
    return rows


def _authorize_payment(order, amount, provider="gateway", metadata=None):
    """Create a Payment row in the pending state.

    The actual gateway call is abstracted here so it can be swapped for a
    real provider SDK later. Returns the Payment instance.
    """
    return Payment.objects.create(
        order=order,
        provider=provider,
        amount=amount,
        status="pending",
        metadata=metadata or {},
    )


@transaction.atomic
def checkout(user, items_data, provider="gateway", metadata=None):
    """Create an order from the user's cart/selected items and authorize payment.

    Payment is accepted *before* stock is committed. Stock is only decremented
    later, in verify_payment(), once the payment is confirmed captured. This
    avoids selling items the customer already paid for but can no longer ship.
    """
    rows = _validate_items(items_data)

    order = Order.objects.create(user=user, status="pending")
    total = Decimal("0.00")
    for row in rows:
        OrderItem.objects.create(
            order=order,
            product_name=row["product"].name,
            unit_price=row["unit_price"],
            quantity=row["quantity"],
        )
        total += row["unit_price"] * row["quantity"]
    order.total = total
    order.save()

    payment = _authorize_payment(order, total, provider=provider, metadata=metadata)
    return order, payment


@transaction.atomic
def verify_payment(order_id, external_id, provider="gateway"):
    """Confirm a previously authorized payment and allocate stock.

    Flow:
      1. Lock the order row and locate the matching Payment.
      2. If the payment is already captured, it is idempotent — return as-is.
      3. Re-check stock for every line under row locks. If any line has
         insufficient stock, the payment is marked failed, the order is
         marked failed, and the authorization is voided/refunded upstream.
      4. Otherwise, stock is decremented, the payment is captured, and the
         order moves to processing.
    """
    order = get_object_or_404(Order, pk=order_id)
    payment = get_object_or_404(
        Payment, order=order, external_id=external_id, provider=provider
    )

    if payment.status == "captured":
        return order, payment, "already_captured"

    # Re-check stock under row locks so concurrent verifications cannot
    # oversell. OrderItem stores a snapshot (product_name), not a FK, so we
    # match by name to find the live Product row for stock checks.
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
        payment.metadata = {**payment.metadata, "insufficient": insufficient}
        payment.save()
        order.status = "failed"
        order.save()
        # Upstream gateway void/refund happens here in a real provider SDK.
        return order, payment, "stock_out"

    # Allocate stock and capture the payment.
    for item in order.items.all():
        product = Product.objects.select_for_update().get(
            name=item.product_name, is_active=True
        )
        product.stock = max(0, product.stock - item.quantity)
        product.save()

    payment.status = "captured"
    payment.save()
    order.status = "processing"
    order.save()
    return order, payment, "captured"


def cancel_order(order_id, user=None):
    """Cancel an order. Refunds are handled by the payment provider."""
    order = get_object_or_404(Order, pk=order_id)
    if user is not None and order.user_id != user.id:
        raise CheckoutError("Order not found.")
    if order.status in ("pending", "processing"):
        order.status = "cancelled"
        order.save()
    return order