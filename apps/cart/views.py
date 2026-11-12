from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from apps.catalog.models import Product
from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer


def get_or_create_active_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user, defaults={'is_active': True})
    if not cart.is_active:
        cart.is_active = True
        cart.save()
    return cart


@extend_schema(tags=["Cart"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart(request):
    cart = get_or_create_active_cart(request.user)
    serializer = CartSerializer(cart)
    return Response(serializer.data)


@extend_schema(tags=["Cart"])
@api_view(['POST', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def cart_item(request, items=None):
    cart = get_or_create_active_cart(request.user)

    if request.method == 'POST':
        product_id = request.data.get('product_id') or request.data.get('product')
        quantity = request.data.get('quantity', 1)
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        if quantity <= 0:
            return Response({'detail': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(pk=product_id)
        except (Product.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not product.is_active:
            return Response({'detail': 'Product is inactive.'}, status=status.HTTP_400_BAD_REQUEST)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        product_id = request.data.get('product_id') or request.data.get('product')
        quantity = request.data.get('quantity')
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        if quantity <= 0:
            return Response({'detail': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        cart_item = None
        try:
            if items is not None:
                cart_item = CartItem.objects.get(pk=items, cart=cart)
        except (CartItem.DoesNotExist, ValueError, TypeError):
            pass
        if cart_item is None and product_id:
            try:
                product = Product.objects.get(pk=product_id)
                cart_item = CartItem.objects.get(cart=cart, product=product)
            except Exception:
                cart_item = None
        if cart_item is None:
            return Response({'detail': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)
        cart_item.quantity = quantity
        cart_item.save()
        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=["Cart"])
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cart_item_remove(request, items=None):
    cart = get_or_create_active_cart(request.user)
    product_id = request.data.get('product_id') or request.data.get('product')
    cart_item = None
    try:
        if items is not None:
            cart_item = CartItem.objects.get(pk=items, cart=cart)
    except (CartItem.DoesNotExist, ValueError, TypeError):
        pass
    if cart_item is None and product_id:
        try:
            product = Product.objects.get(pk=product_id)
            cart_item = CartItem.objects.get(cart=cart, product=product)
        except Exception:
            cart_item = None
    if cart_item is None:
        return Response({'detail': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)
    cart_item.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
