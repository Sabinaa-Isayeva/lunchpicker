from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction

from core.models import SystemSettings
from core.permissions import IsAdminUserOrReadOnly
from core.serializers import SystemSettingsSerializer
from core.utils import audit


class SystemSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly]

    def get(self, request):
        return Response(SystemSettingsSerializer(SystemSettings.current()).data)

    @transaction.atomic
    def patch(self, request):
        instance = SystemSettings.current()
        if instance.pk is None:
            instance, _ = SystemSettings.objects.get_or_create(pk=1)
        instance = SystemSettings.objects.select_for_update().get(pk=instance.pk)
        serializer = SystemSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit("settings.update", request.user)
        return Response(serializer.data)
