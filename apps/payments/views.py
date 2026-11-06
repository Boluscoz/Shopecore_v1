from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize(request):
    order_id = request.data.get("order_id")
    currency = request.data.get("currency", "NGN")
    try:
        payment = services.initialize(
            order_id, currency=currency, metadata=request.data
        )
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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
        status=status.HTTP_201_CREATED,
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
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status(request, reference):
    try:
        payload = services.customer_status(reference)
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook(request):
    payload = request.body.decode("utf-8")
    signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    try:
        result = services.handle_webhook(payload, signature)
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refund(request, order_id):
    try:
        payment = services.refund(
            order_id, reason=request.data.get("reason", "")
        )
    except services.PaymentError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "id": payment.id,
            "status": payment.status,
            "external_id": payment.external_id,
            "amount": str(payment.amount),
        }
    )