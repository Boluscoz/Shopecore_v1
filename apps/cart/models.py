from django.db import models
from django.conf import settings
from apps.catalog.models import Product
from django.db.models import Sum


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user_id})"

    @property
    def total(self):
        # total = sum(item.subtotal for item in self.items.all())
        # return total
        result = self.items.aggregate(grand_total=Sum('subtotal'))[
            'grand_total']
        return result or 0


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'product')
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'product'], name='unique_cart_product')
        ]

    def __str__(self):
        return f"{self.product_id} x {self.quantity}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity
