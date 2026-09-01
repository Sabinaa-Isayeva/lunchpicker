from rest_framework import serializers

from restaurants.models import MenuItem, Restaurant


class MenuItemSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.all(), required=False
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
