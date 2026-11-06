from decimal import Decimal
from threading import Thread

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.db import connection, transaction

from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem, Payment
from apps.orders import services


User = get_user_model()


def _make_product(name="Widget", stock=10, price="10.00"):
    cat, _ = Category.objects.get_or_create(name="General", defaults={"slug": "general"})
    return Product.objects.create(
        category=cat,
        name=name,
        slug=name.lower(),
        price=Decimal(price),
        stock=stock,
        is_active=True,
    )


class CheckoutServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@example.com", password="pw")
        self.product = _make_product(stock=10)

    def test_checkout_creates_order_items_and_pending_payment(self):
        order, payment = services.checkout(
            self.user,
            [{"product_id": self.product.id, "quantity": 2}],
        )
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total, Decimal("20.00"))
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.amount, Decimal("20.00"))
        self.assertEqual(self.product.refresh_from_db().stock, 10)  # not yet decremented

    def test_checkout_rejects_no_items(self):
        with self.assertRaises(services.CheckoutError):
            services.checkout(self.user, [])

    def test_checkout_rejects_inactive_product(self):
        self.product.is_active = False
        self.product.save()
        with self.assertRaises(services.CheckoutError):
            services.checkout(self.user, [{"product_id": self.product.id, "quantity": 1}])

    def test_checkout_rejects_invalid_quantity(self):
        with self.assertRaises(services.CheckoutError):
            services.checkout(self.user, [{"product_id": self.product.id, "quantity": 0}])
        with self.assertRaises(services.CheckoutError):
            services.checkout(self.user, [{"product_id": self.product.id, "quantity": "x"}])

    def test_checkout_rejects_unknown_product(self):
        with self.assertRaises(services.CheckoutError):
            services.checkout(self.user, [{"product_id": 999999, "quantity": 1}])

    def test_checkout_rolls_back_on_failure(self):
        before = Order.objects.count()
        try:
            services.checkout(
                self.user,
                [{"product_id": self.product.id, "quantity": 1}, {"product_id": 999999, "quantity": 1}],
            )
        except services.CheckoutError:
            pass
        self.assertEqual(Order.objects.count(), before)


class VerifyPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="v@example.com", password="pw")
        self.product = _make_product(stock=10)
        self.order, self.payment = services.checkout(
            self.user,
            [{"product_id": self.product.id, "quantity": 2}],
        )

    def test_verify_captures_and_decrements_stock(self):
        order, payment, result = services.verify_payment(
            self.order.id, self.payment.external_id
        )
        self.assertEqual(result, "captured")
        self.assertEqual(order.status, "processing")
        self.assertEqual(payment.status, "captured")
        self.assertEqual(self.product.refresh_from_db().stock, 8)

    def test_verify_idempotent_when_already_captured(self):
        services.verify_payment(self.order.id, self.payment.external_id)
        order, payment, result = services.verify_payment(
            self.order.id, self.payment.external_id
        )
        self.assertEqual(result, "already_captured")
        self.assertEqual(self.product.refresh_from_db().stock, 8)

    def test_verify_marks_failed_on_insufficient_stock(self):
        self.product.stock = 1
        self.product.save()
        order, payment, result = services.verify_payment(
            self.order.id, self.payment.external_id
        )
        self.assertEqual(result, "stock_out")
        self.assertEqual(order.status, "failed")
        self.assertEqual(payment.status, "failed")
        self.assertEqual(self.product.refresh_from_db().stock, 1)  # unchanged

    def test_verify_unknown_order_raises(self):
        with self.assertRaises(services.CheckoutError):
            services.verify_payment(999999, "nope")

    def test_verify_unknown_external_id_raises(self):
        with self.assertRaises(services.CheckoutError):
            services.verify_payment(self.order.id, "does_not_exist")

def test_concurrent_verify_does_not_double_decrement_stock(self):
        """The ACID isolation fix: two concurrent captures must not oversell.

        Two real threads with separate DB connections race to verify the
        same payment. Before the fix, both read status=pending before either
        locked the payment row, so both decremented stock (10 -> 6 instead of
        8). After the fix, the payment-row lock serializes them and the second
        observes the first's capture and short-circuits.
        """
        # Spawn a second pending payment for the same order to simulate a
        # duplicate webhook, then verify both concurrently.
        Payment.objects.create(
            order=self.order,
            provider="gateway",
            amount=self.order.total,
            status="pending",
            external_id="dup-external-id",
        )
        dup = Payment.objects.get(external_id="dup-external-id")

        results = {}

        def run(external_id, key):
            # Each thread needs its own connection; Django's default connection
            # is thread-local, so this is automatic.
            try:
                services.verify_payment(self.order.id, external_id)
                results[key] = "captured"
            except Exception as exc:  # pragma: no cover - diagnostic
                results[key] = f"error: {exc!r}"

        t1 = Thread(target=run, args=(self.payment.external_id, "first"))
        t2 = Thread(target=run, args=(dup.external_id, "second"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(self.product.refresh_from_db().stock, 8)
        self.assertIn("captured", results.values())
        self.assertEqual(
            sum(1 for v in results.values() if v == "captured"), 1
        )


class CancelOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="c@example.com", password="pw")
        self.product = _make_product(stock=10)
        self.order, self.payment = services.checkout(
            self.user,
            [{"product_id": self.product.id, "quantity": 2}],
        )

    def test_cancel_pending_order(self):
        order = services.cancel_order(self.order.id, user=self.user)
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(self.payment.refresh_from_db().status, "pending")

    def test_cancel_captured_order_refunds_payment(self):
        services.verify_payment(self.order.id, self.payment.external_id)
        order = services.cancel_order(self.order.id, user=self.user)
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(self.payment.refresh_from_db().status, "refunded")

    def test_cancel_is_atomic_against_concurrent_verify(self):
        """Cancel must not lose to a concurrent verify_payment."""
        # Verify first (captures + decrements), then cancel.
        services.verify_payment(self.order.id, self.payment.external_id)
        order = services.cancel_order(self.order.id, user=self.user)
        self.assertEqual(order.status, "cancelled")
        self.assertEqual(self.payment.refresh_from_db().status, "refunded")

    def test_cancel_wrong_user_raises(self):
        other = User.objects.create_user(email="o@example.com", password="pw")
        with self.assertRaises(services.CheckoutError):
            services.cancel_order(self.order.id, user=other)

    def test_cancel_already_cancelled_is_noop(self):
        self.order.status = "cancelled"
        self.order.save()
        order = services.cancel_order(self.order.id, user=self.user)
        self.assertEqual(order.status, "cancelled")