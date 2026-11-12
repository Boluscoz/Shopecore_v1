from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product
from .models import Order, OrderItem
import logging


logger = logging.getLogger("apps.orders")


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


@transaction.atomic
def create_order(user, items_data):
    """Create an order with its line items. Returns (order, total).

    Payment initialization is delegated to apps.payments.services so the
    order row and the payment row live in separate services. Order state
    stays 'pending' here; only the Payment row is created later.
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
    return order, total


@transaction.atomic
def apply_payment_result(order_id, result, insufficient=None):
    """Transition order state based on a payment decision.

    Kept here so the order state machine stays in the orders service while
    the payment decision lives in the payments service. Order state and
    payment state are kept distinct: this only ever touches Order.status.
    """
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise CheckoutError("Order not found.")

    if result == "captured":
        order.status = "processing"
    elif result == "stock_out":
        order.status = "failed"
    elif result == "failed":
        order.status = "failed"
    else:
        return order  # already_captured / no-op
    order.save()
    return order


@transaction.atomic
def set_order_cancelled(order_id, user=None):
    """Cancel an order. Refunds are handled by the payment provider."""
    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise CheckoutError("Order not found.")

    if user is not None and order.user_id != user.id:
        raise CheckoutError("Order not found.")

    if order.status not in ("pending", "processing"):
        return order

    order.status = "cancelled"
    order.save()
    return order
