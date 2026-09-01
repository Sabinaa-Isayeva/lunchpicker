from rest_framework import serializers
from sessions.models import SelectionResult

class LunchHistorySerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(source="session.end_time", read_only=True)
    session_title = serializers.CharField(source="session.title", read_only=True)
    team_name = serializers.CharField(source="session.team.name", read_only=True)
    restaurant_name = serializers.CharField(source="selected_proposal.restaurant.name", read_only=True)
    cuisine_type = serializers.CharField(source="selected_proposal.restaurant.cuisine_type", read_only=True)
    average_price = serializers.DecimalField(
        source="selected_proposal.restaurant.average_price", max_digits=6, decimal_places=2, read_only=True
    )
    method_display = serializers.CharField(source="get_method_used_display", read_only=True)

    class Meta:
        model = SelectionResult
        fields = [
            "id", "date", "session_title", "team_name", "restaurant_name",
            "cuisine_type", "average_price", "method_used", "method_display", "executed_at",
        ]
