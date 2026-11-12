from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Order
from .services import CheckoutError, create_order, set_order_cancelled
from .serializers import OrderSerializer
from apps.payments import services as payment_services


@extend_schema(
    tags=["Orders"]
)
def _payment_payload(payment):
    return {
        "id": payment.id,
        "provider": payment.provider,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "external_id": payment.external_id,
    }


@extend_schema(tags=["Orders"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def orders(request):
    queryset = Order.objects.filter(user=request.user)
    serializer = OrderSerializer(queryset, many=True)
    return Response(serializer.data)


@extend_schema(tags=["Orders"])
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


@extend_schema(tags=["Orders"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout(request):
    items_data = request.data.get("items") or []
    currency = request.data.get("currency", "NGN")
    try:
        order, total = create_order(request.user, items_data)
        payment = payment_services.initialize(
            order.id, currency=currency, metadata=request.data
        )
    except (CheckoutError, payment_services.PaymentError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    serializer = OrderSerializer(order)
    return Response(
        {
            "order": serializer.data,
            "payment": _payment_payload(payment),
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["Orders"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    try:
        order = set_order_cancelled(pk, user=request.user)
    except CheckoutError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    serializer = OrderSerializer(order)
    return Response(serializer.data)
