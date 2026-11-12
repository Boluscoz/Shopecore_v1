from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from . import services
from . import serializers
import logging

logger = logging.getLogger("apps.payments.views")


@extend_schema(
    tags=["Payments"],
    operation_id="payment_initialize",
    request=serializers.PaymentInitializeRequestSerializer,
    responses={
        201: serializers.PaymentInitializeResponseSerializer,
        400: serializers.ErrorResponseSerializer,
    },
    description=(
        "Initialize a payment for an order. Creates a Payment row in 'pending' state "
        "and returns the provider access code for the customer to complete checkout."
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize(request):
    order_id = request.data.get("order_id")
    logger.info(
        "api.payment.initialize.requested",
        extra={"user_id": request.user.id, "order_id": order_id},
    )
    currency = request.data.get("currency", "NGN")
    try:
        payment = services.initialize(
            order_id, currency=currency, metadata=request.data
        )
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "id": payment.id,
            "provider": payment.provider,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "external_id": payment.external_id,
            "access_code": payment.metadata.get("access_code"),
        },
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Payments"],
    operation_id="payment_verify",
    request=serializers.PaymentVerifyRequestSerializer,
    responses={
        200: serializers.PaymentVerifyResponseSerializer,
        404: serializers.ErrorResponseSerializer,
    },
    description=(
        "Verify a payment authorization server-side against the provider, allocate stock, "
        "and capture the payment. Returns the order, payment, and result."
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify(request):
    order_id = request.data.get("order_id")
    reference = request.data.get("reference")
    provider = request.data.get("provider", "paystack")
    try:
        order, payment, result = services.verify_provider_reference(
            order_id, reference, provider=provider
        )
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(
        {
            "order": {
                "id": order.id,
                "status": order.status,
                "total": str(order.total),
            },
            "payment": {
                "id": payment.id,
                "status": payment.status,
                "external_id": payment.external_id,
                "amount": str(payment.amount),
            },
            "result": result,
        }
    )


@extend_schema(
    tags=["Payments"],
    operation_id="payment_status",
    parameters=[
        OpenApiParameter(
            name="reference",
            type=str,
            location=OpenApiParameter.PATH,
            description="Paystack transaction reference (external_id).",
        )
    ],
    responses={
        200: serializers.PaymentStatusResponseSerializer,
        404: serializers.ErrorResponseSerializer,
    },
    description=(
        "Look up a customer's payment status by provider reference. "
        "Re-verifies amount, currency and final status server-side before returning."
    ),
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status(request, reference):
    try:
        payload = services.customer_status(reference)
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_404_NOT_FOUND)
    payment = payload["payment"]
    return Response(
        {
            "payment": {
                "id": payment.id,
                "status": payment.status,
                "external_id": payment.external_id,
                "amount": str(payment.amount),
            },
            "provider_status": payload["provider_status"],
            "verified": payload["verified"],
        }
    )


@extend_schema(
    tags=["Payments"],
    operation_id="payment_webhook",
    request=None,
    responses={
        200: serializers.PaymentWebhookResponseSerializer,
        400: serializers.ErrorResponseSerializer,
    },
    description=(
        "Process a Paystack webhook. The raw JSON body and X-Paystack-Signature header "
        "are verified before any state change. Idempotent for already-processed events."
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook(request):
    payload = request.body.decode("utf-8")
    signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    try:
        result = services.handle_webhook(payload, signature)
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
    return Response(result)


@extend_schema(
    tags=["Payments"],
    operation_id="payment_refund",
    parameters=[
        OpenApiParameter(
            name="order_id",
            type=int,
            location=OpenApiParameter.PATH,
            description="ID of the order to refund.",
        )
    ],
    request=serializers.PaymentRefundRequestSerializer,
    responses={
        200: serializers.PaymentRefundResponseSerializer,
        400: serializers.ErrorResponseSerializer,
    },
    description=(
        "Refund a captured payment. Only payments in 'captured' state can be refunded."
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refund(request, order_id):
    try:
        payment = services.refund(
            order_id, reason=request.data.get("reason", "")
        )
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "id": payment.id,
            "status": payment.status,
            "external_id": payment.external_id,
            "amount": str(payment.amount),
        }
    )
