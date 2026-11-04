from django.urls import path
from . import views

urlpatterns = [
    path("orders", views.orders, name="orders"),
    path("orders/checkout", views.checkout, name="checkout"),
    path("orders/<int:pk>", views.order_detail, name="order_detail"),
    path(
        "orders/<int:pk>/verify-payment",
        views.verify_payment,
        name="verify-payment",
    ),
    path(
        "orders/<int:pk>/cancel",
        views.cancel_order,
        name="cancel-order",
    ),
]