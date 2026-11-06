from django.db import models

# Payment lives in apps.orders.models so the migration and the FK from the
# payments service stay in one place. See apps/payments/services.py.