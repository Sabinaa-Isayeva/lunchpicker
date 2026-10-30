from rest_framework import serializers
from django.shortcuts import get_object_or_404

from restaurants.models import MenuItem, Restaurant


class URLRestaurantDefault:
    requires_context = True

    def __call__(self, field):
        return get_object_or_404(Restaurant, pk=field.context["view"].kwargs["restaurant_pk"])


class MenuItemSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.all(), required=False, default=URLRestaurantDefault()
    )

    class Meta:
        model = MenuItem
        fields = [
            "id", "restaurant", "restaurant_name", "name", "description", "price",
            "is_vegetarian", "is_vegan", "is_gluten_free",
        ]

    def validate_restaurant(self, value):
        view = self.context.get("view")
        parent_id = (view.kwargs or {}).get("restaurant_pk") if view else None
        if parent_id and value.pk != int(parent_id):
            raise serializers.ValidationError("Menu item must belong to the URL restaurant.")
        return value


class RestaurantSerializer(serializers.ModelSerializer):
    average_price = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0, required=False)
    rating = serializers.DecimalField(max_digits=3, decimal_places=1, min_value=0, max_value=5, required=False)
    menu_items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = Restaurant
        fields = [
            "id", "name", "address", "cuisine_type", "website_url",
            "average_price", "rating", "created_by", "menu_items", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        address = attrs.get("address", getattr(self.instance, "address", ""))
        existing = Restaurant.objects.filter(name__iexact=name, address__iexact=address)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A restaurant with this name and address already exists.")
        return attrs
