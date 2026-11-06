from django.urls import path
from . import views

urlpatterns = [
    path("initialize", views.initialize, name="payment-initialize"),
    path("verify", views.verify, name="payment-verify"),
    path("status/<str:reference>", views.status, name="payment-status"),
    path("webhook", views.webhook, name="payment-webhook"),
    path("<int:order_id>/refund", views.refund, name="payment-refund"),
]