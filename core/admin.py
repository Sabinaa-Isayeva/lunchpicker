from django.contrib import admin
from core.models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("default_selection_algorithm", "default_voting_mode", "allow_anonymous_voting", "updated_at")
    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
