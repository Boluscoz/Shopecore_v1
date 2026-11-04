from rest_framework import serializers
from apps.orders.models import Order, OrderItem, Payment


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_name",
            "unit_price",
            "quantity",
            "line_total",
        )
        read_only_fields = ("id", "line_total")


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "provider",
            "amount",
            "status",
            "external_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "total",
            "items",
            "payments",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "total", "created_at", "updated_at")

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = Order.objects.create(**validated_data)
        total = 0
        for item_data in items_data:
            item = OrderItem.objects.create(order=order, **item_data)
            total += float(item.line_total)
        order.total = round(total, 2)
        order.save()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        instance.status = validated_data.get("status", instance.status)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            total = 0
            for item_data in items_data:
                item = OrderItem.objects.create(instance, **item_data)
                total += float(item.line_total)
            instance.total = round(total, 2)
            instance.save()
        return instance