from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Order
from .services import (
    CheckoutError,
    checkout as checkout_service,
    cancel_order as cancel_order_service,
    verify_payment as verify_payment_service,
)
from .serializers import OrderSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def orders(request):
    queryset = Order.objects.filter(user=request.user)
    serializer = OrderSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def order_detail(request, pk):
    order = (
        Order.objects.filter(pk=pk, user=request.user)
        .select_related()
        .first()
    )
    if order is None:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    serializer = OrderSerializer(order, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout(request):
    items_data = request.data.get("items") or []
    provider = request.data.get("provider", "gateway")
    try:
        order, payment = checkout_service(
            request.user, items_data, provider=provider
        )
    except CheckoutError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    serializer = OrderSerializer(order)
    return Response(
        {
            "order": serializer.data,
            "payment": {
                "id": payment.id,
                "provider": payment.provider,
                "amount": str(payment.amount),
                "status": payment.status,
                "external_id": payment.external_id,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_payment(request, pk):
    """Confirm a payment authorization and allocate stock.

    Called by the payment provider's webhook/callback. Stock is only
    decremented once the payment is captured; if stock is short, the order
    and payment are marked failed instead of overselling.
    """
    external_id = request.data.get("external_id")
    provider = request.data.get("provider", "gateway")
    if not external_id:
        return Response(
            {"detail": "external_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    order, payment, result = verify_payment_service(
        pk, external_id, provider=provider
    )
    serializer = OrderSerializer(order)
    return Response(
        {
            "order": serializer.data,
            "payment": {
                "id": payment.id,
                "provider": payment.provider,
                "amount": str(payment.amount),
                "status": payment.status,
                "external_id": payment.external_id,
            },
            "result": result,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    try:
        order = cancel_order_service(pk, user=request.user)
    except CheckoutError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    serializer = OrderSerializer(order)
    return Response(serializer.data)