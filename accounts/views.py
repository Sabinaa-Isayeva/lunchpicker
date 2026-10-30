from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.utils import audit
from accounts.serializers import UserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    filterset_fields = ["username", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return User.objects.all().order_by("id")
        return User.objects.filter(pk=user.pk).order_by("id")

    def perform_update(self, serializer):
        user = serializer.save()
        audit("user.update", self.request.user, f"user_id={user.pk}")

    def destroy(self, request, *args, **kwargs):
        from rest_framework.exceptions import PermissionDenied
        if not request.user.is_staff:
            raise PermissionDenied("Only administrators can delete accounts.")
        if self.get_object().pk == request.user.pk:
            raise PermissionDenied("You cannot delete your own administrator account.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="me", permission_classes=[])
    def me(self, request):
        if not request.user.is_authenticated:
            from rest_framework.exceptions import NotAuthenticated
            raise NotAuthenticated()
        return Response(self.get_serializer(request.user).data)

    def get_permissions(self):
        if self.action == "create":
            self.permission_classes = []
        return super().get_permissions()
