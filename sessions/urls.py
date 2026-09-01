from django.urls import include, path
from rest_framework.routers import DefaultRouter

from sessions.views import LunchSessionViewSet, NotificationViewSet, SuggestionViewSet

router = DefaultRouter()
router.register("sessions", LunchSessionViewSet, basename="session")
router.register("suggestions", SuggestionViewSet, basename="suggestion")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]
