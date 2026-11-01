from django.urls import path
from . import views

urlpatterns = [
    path('categories', views.categories, name='categories'),
    path('categories/<int:pk>', views.category_detail, name='category_detail'),
    path('categories/<int:pk>/deactivate', views.category_deactivate, name='category_deactivate'),
    path('products', views.products, name='products'),
    path('products/<int:pk>', views.product_detail, name='product_detail'),
    path('products/<int:pk>/deactivate', views.product_deactivate, name='product_deactivate'),
]
