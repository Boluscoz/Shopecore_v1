from django.urls import path
from . import views

urlpatterns = [
    path('cart', views.cart, name='cart'),
    path('cart/items', views.cart_item, name='cart_items'),
    path('cart/item/<str:items>', views.cart_item, name='cart_item'),
    path('cart/items/<str:items>', views.cart_item, name='cart_item_detail'),
    path('cart/items/<str:items>/remove', views.cart_item_remove, name='cart_item_remove'),
]

