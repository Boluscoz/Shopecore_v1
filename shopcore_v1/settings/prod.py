from .base import *
import os


DEBUG = False

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

ALLOWED_HOSTS = []

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('HOST'),
        'PORT': os.environ.get('PORT')
    }
}

# Paystack keys
PAYSTACK = {
    'SECRET_KEY': os.environ.get('Pk_secret_live_key'),
    'PUBLIC_KEY': os.environ.get('Pk_public_live_key'),
    'ENVIRONMENT': os.environ.get('Pk_ENVIRONMENT', 'prod'),
}


# CSRF_COOKIE_SECURE = True

# SESSION_COOKIE_SECURE = True

# # SECURE_SSL_REDIRECT = True

# # SECURE_HSTS_SECONDS = 31536000

# # SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# # SECURE_CONTENT_TYPE_NOSNIFF = True

# # X_FRAME_OPTIONS = 'DENY'


LOGGING["loggers"]["apps.payments"]["level"] = "WARNING"
LOGGING["loggers"]["apps.orders"]["level"] = "INFO"
