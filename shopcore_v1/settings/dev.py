from .base import *

DEBUG = True


# Allowed_Hosts
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

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
    'SECRET_KEY': os.environ.get('Pk_secret_key'),
    'PUBLIC_KEY': os.environ.get('Pk_public_key'),
    'ENVIRONMENT': os.environ.get('Pk_ENVIRONMENT', 'test'),
}

# Dev log levels (base.py LOGGING config applies with console + file handlers)
LOGGING["loggers"]["apps.payments"]["level"] = "DEBUG"
LOGGING["loggers"]["apps.orders"]["level"] = "DEBUG"
