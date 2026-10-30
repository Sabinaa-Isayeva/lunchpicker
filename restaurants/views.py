from rest_framework import viewsets
from django.shortcuts import get_object_or_404

from core.permissions import IsAdminUserOrReadOnly
from restaurants.models import MenuItem, Restaurant
from restaurants.serializers import MenuItemSerializer, RestaurantSerializer


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.prefetch_related("menu_items")
    serializer_class = RestaurantSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    filterset_fields = ["cuisine_type"]
    search_fields = ["name", "address", "menu_items__name"]
    ordering_fields = ["name", "average_price", "rating"]


class MenuItemViewSet(viewsets.ModelViewSet):
    serializer_class = MenuItemSerializer
    permission_classes = [IsAdminUserOrReadOnly]

    def get_queryset(self):
        return MenuItem.objects.filter(restaurant_id=self.kwargs["restaurant_pk"])

    def perform_create(self, serializer):
        restaurant = get_object_or_404(Restaurant, pk=self.kwargs["restaurant_pk"])
        serializer.save(restaurant=restaurant)
