from django.urls import include, path
from rest_framework.routers import DefaultRouter

from restaurants.views import MenuItemViewSet, RestaurantViewSet

router = DefaultRouter()
router.register("restaurants", RestaurantViewSet, basename="restaurant")
router.register(
    r"restaurants/(?P<restaurant_pk>\d+)/menu-items",
    MenuItemViewSet,
    basename="menu-item",
)

urlpatterns = [
    path("", include(router.urls)),
]
