from rest_framework import serializers
from core.models import SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    default_voting_mode = serializers.ChoiceField(choices=["single", "multiple", "rating"])
    voting_deadline_minutes = serializers.IntegerField(min_value=1, max_value=10080)
    weighted_base_weight = serializers.IntegerField(min_value=1, max_value=1000)

    class Meta:
        model = SystemSettings
        fields = ["default_selection_algorithm", "default_voting_mode", "voting_deadline_minutes",
                  "allow_anonymous_voting", "weighted_base_weight", "updated_at"]
        read_only_fields = ["updated_at"]
