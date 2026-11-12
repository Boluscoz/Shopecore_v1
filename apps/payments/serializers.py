from rest_framework import serializers


class PaymentInitializeRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(help_text="ID of the order to initialize payment for.")
    currency = serializers.CharField(default="NGN", max_length=3, help_text="Transaction currency code.")
    customer_email = serializers.EmailField(help_text="Customer's email address.")


class PaymentInitializeResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    provider = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    status = serializers.CharField()
    external_id = serializers.CharField()
    access_code = serializers.CharField(allow_null=True)


class PaymentVerifyRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(help_text="ID of the order to verify payment for.")
    reference = serializers.CharField(help_text="Paystack transaction reference.")
    provider = serializers.CharField(default="paystack", max_length=50, help_text="Payment provider name.")


class PaymentVerifyResponseSerializer(serializers.Serializer):
    order = serializers.DictField()
    payment = serializers.DictField()
    result = serializers.CharField()


class PaymentStatusResponseSerializer(serializers.Serializer):
    payment = serializers.DictField()
    provider_status = serializers.CharField(allow_null=True)
    verified = serializers.BooleanField()


class PaymentWebhookResponseSerializer(serializers.Serializer):
    event = serializers.CharField()
    reference = serializers.CharField()
    action = serializers.CharField()


class PaymentRefundRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(help_text="ID of the order to refund.")
    reason = serializers.CharField(required=False, default="", help_text="Refund reason note.")


class PaymentRefundResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    external_id = serializers.CharField()
    amount = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
