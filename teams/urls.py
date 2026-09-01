from django.urls import include, path
from rest_framework.routers import DefaultRouter

from teams.views import JoinTeamPreviewView, JoinTeamView, TeamViewSet

router = DefaultRouter()
router.register("teams", TeamViewSet, basename="team")

urlpatterns = [
    path("join/<uuid:token>/preview/", JoinTeamPreviewView.as_view(), name="join-preview"),
    path("join/<uuid:token>/", JoinTeamView.as_view(), name="join-team"),
    path("", include(router.urls)),
]
