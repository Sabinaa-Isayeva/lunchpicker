from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="frontend"),
    path("food-admin/", TemplateView.as_view(template_name="food_admin.html"), name="food-admin"),
    path("admin-panel/", TemplateView.as_view(template_name="admin_panel.html"), name="admin-panel"),
    path("join/<uuid:token>/", TemplateView.as_view(template_name="join.html"), name="join-page"),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("restaurants.urls")),
    path("api/", include("sessions.urls")),
    path("api/", include("analytics.urls")),
    path("api/", include("teams.urls")),
]
