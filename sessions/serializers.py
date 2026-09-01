from django.utils import timezone
from rest_framework import serializers

from restaurants.models import MenuItem
from restaurants.serializers import MenuItemSerializer
from sessions.models import (
    LunchSession,
    Notification,
    SelectionResult,
    SessionProposal,
    Suggestion,
    Vote,
)
from teams.models import Membership, Team


class TeamMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name"]


class LunchSessionSerializer(serializers.ModelSerializer):
    team = TeamMiniSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(), source="team", write_only=True
    )
    proposal_count = serializers.IntegerField(source="proposals.count", read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = LunchSession
        fields = [
            "id", "team", "team_id", "title", "start_time", "end_time",
            "is_recurring", "recurrence_rule", "selection_algorithm",
            "is_anonymous", "voting_mode", "is_announcement",
            "created_by", "proposal_count", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def get_is_active(self, obj):
        return obj.is_active

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "end_time must be after start_time."})
        is_recurring = attrs.get("is_recurring", getattr(self.instance, "is_recurring", False))
        recurrence_rule = attrs.get("recurrence_rule", getattr(self.instance, "recurrence_rule", ""))
        if is_recurring and recurrence_rule not in LunchSession.RecurrenceRule.values:
            raise serializers.ValidationError({"recurrence_rule": "Recurrence rule is required for recurring sessions."})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        team = validated_data["team"]
        if not (user.is_staff or team.created_by_id == user.pk):
            raise serializers.ValidationError("Only the team owner can schedule sessions.")
        if not team.members.filter(pk=user.pk).exists():
            Membership.objects.create(team=team, user=user, role=Membership.Role.OWNER)
        validated_data["created_by"] = user
        return super().create(validated_data)


class SessionProposalSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    restaurant_address = serializers.CharField(source="restaurant.address", read_only=True)
    cuisine_type = serializers.CharField(source="restaurant.cuisine_type", read_only=True)
    average_price = serializers.DecimalField(
        source="restaurant.average_price", max_digits=6, decimal_places=2, read_only=True
    )
    menu_items_detail = serializers.SerializerMethodField()
    vote_count = serializers.IntegerField(source="votes.count", read_only=True)
    proposer_name = serializers.CharField(source="proposer.get_full_name", read_only=True)

    class Meta:
        model = SessionProposal
        fields = [
            "id", "session", "restaurant", "restaurant_name", "restaurant_address",
            "cuisine_type",
            "average_price", "menu_items", "menu_items_detail", "proposer",
            "proposer_name", "vote_count", "created_at",
        ]
        read_only_fields = ["id", "proposer", "created_at"]

    def get_menu_items_detail(self, obj):
        return MenuItemSerializer(obj.menu_items.all(), many=True).data

    def create(self, validated_data):
        validated_data["proposer"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, attrs):
        session = attrs.get("session") or getattr(self.instance, "session", None)
        restaurant = attrs.get("restaurant")
        if session and not session.is_active:
            raise serializers.ValidationError("Proposals are only accepted while the session is active.")
        if restaurant and restaurant.proposals.filter(session=session, restaurant=restaurant).exclude(
                pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("This restaurant is already proposed in this session.")
        if session:
            user = self.context["request"].user
            membership = Membership.objects.filter(team=session.team, user=user).first()
            if not (user.is_staff or (membership and membership.role != Membership.Role.GUEST)):
                raise serializers.ValidationError("Guests have read-only access and cannot propose.")
        return attrs


class VoteSerializer(serializers.ModelSerializer):
    voter_username = serializers.CharField(source="voter.username", read_only=True)
    proposal_restaurant = serializers.CharField(source="proposal.restaurant.name", read_only=True)

    class Meta:
        model = Vote
        fields = ["id", "session", "voter", "voter_username", "proposal",
                  "proposal_restaurant", "choice", "voted_at"]
        read_only_fields = ["id", "voter", "voted_at"]

    def create(self, validated_data):
        validated_data["voter"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, attrs):
        request = self.context["request"]
        session = attrs.get("session") or getattr(self.instance, "session", None)
        proposal = attrs.get("proposal") or getattr(self.instance, "proposal", None)

        if session and proposal and proposal.session_id != session.id:
            raise serializers.ValidationError({"proposal": "Vote must target a proposal within the same session."})

        if session:
            if not session.is_active:
                raise serializers.ValidationError("Voting is only allowed while the session is active.")
            membership = Membership.objects.filter(team=session.team, user=request.user).first()
            if not (request.user.is_staff or (membership and membership.role != Membership.Role.GUEST)):
                raise serializers.ValidationError("Guests have read-only access and cannot vote.")

        recent = Vote.objects.filter(voter=request.user, voted_at__gte=timezone.now() - timezone.timedelta(minutes=1))
        if self.instance:
            recent = recent.exclude(pk=self.instance.pk)
        if recent.count() >= 5:
            raise serializers.ValidationError("Rate limit exceeded: maximum 5 votes per minute.")

        if session and getattr(session, "voting_mode", "rating") == "single":
            other = Vote.objects.filter(session=session, voter=request.user).exclude(proposal=proposal)
            if self.instance:
                other = other.exclude(pk=self.instance.pk)
            if other.exists():
                raise serializers.ValidationError("Single-choice session: you already voted.")

        existing = Vote.objects.filter(session=session, voter=request.user, proposal=proposal)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("You have already voted on this proposal in this session.")
        return attrs


class SuggestionSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    session_title = serializers.CharField(source="session.title", read_only=True)
    menu_items_detail = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Suggestion
        fields = [
            "id", "session", "session_title", "user", "username", "restaurant",
            "restaurant_name", "menu_items", "menu_items_detail", "note",
            "status", "status_display", "admin_note", "created_at",
        ]
        read_only_fields = ["id", "user", "status", "admin_note", "created_at"]

    def get_menu_items_detail(self, obj):
        return MenuItemSerializer(obj.menu_items.all(), many=True).data

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, attrs):
        session = attrs.get("session") or getattr(self.instance, "session", None)
        menu_items = attrs.get("menu_items") or []
        restaurant = attrs.get("restaurant")
        if restaurant:
            for item in menu_items:
                if item.restaurant_id != restaurant.id:
                    raise serializers.ValidationError({"menu_items": "All menu items must belong to the selected restaurant."})
        if session:
            user = self.context["request"].user
            membership = Membership.objects.filter(team=session.team, user=user).first()
            if not session.is_active:
                raise serializers.ValidationError("Suggestions are only accepted while the session is active.")
            if not (user.is_staff or (membership and membership.role != Membership.Role.GUEST)):
                raise serializers.ValidationError("Guests have read-only access and cannot suggest.")
        return attrs


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


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "is_read", "created_at"]


class SelectionResultSerializer(serializers.ModelSerializer):
    restaurant = serializers.CharField(source="selected_proposal.restaurant.name", read_only=True)
    method_display = serializers.CharField(source="get_method_used_display", read_only=True)

    class Meta:
        model = SelectionResult
        fields = ["id", "session", "selected_proposal", "restaurant", "method_used", "method_display", "executed_at"]
