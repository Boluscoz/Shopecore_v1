"""
URL configuration for shopcore_v1 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

infra_urls = [
    path('admin/', admin.site.urls),
]

# 2. Main Customer-Facing Applications
business_urls = [
    path('api/v1/accounts/', include('apps.accounts.urls')),
    path('api/v1/accounts/', include('apps.catalog.urls')),
    path('api/v1/accounts/', include('apps.orders.urls')),
    path('api/v1/accounts/', include('apps.common.urls')),
    path('api/v1/accounts/', include('apps.catalog.urls')),
    path('api/v1/accounts/', include('apps.cart.urls')),
]

urlpatterns = infra_urls + business_urls
