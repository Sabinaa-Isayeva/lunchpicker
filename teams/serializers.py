from django.contrib.auth import get_user_model
from rest_framework import serializers

from teams.models import Membership, Team, TeamInviteToken

User = get_user_model()


class MembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "team", "user", "username", "role", "joined_at"]
        read_only_fields = ["id", "team", "user", "joined_at"]


class TeamSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    member_count = serializers.IntegerField(source="members.count", read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ["id", "name", "description", "created_by", "member_count", "my_role", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_my_role(self, obj):
        membership = obj.memberships.filter(user=self.context["request"].user).first()
        return membership.role if membership else None

    def validate_name(self, value):
        qs = Team.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A team with this name already exists.")
        return value

    def create(self, validated_data):
        team = super().create(validated_data)
        # the M2M "members" is backed by the Membership through table:
        # creating the OWNER Membership row is what adds the user to the team
        Membership.objects.create(team=team, user=team.created_by, role=Membership.Role.OWNER)
        return team


class InviteSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.ChoiceField(choices=Membership.Role.choices, default=Membership.Role.MEMBER)

    def validate_username(self, value):
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No such user.")
        return value


class InviteLinkSerializer(serializers.ModelSerializer):
    days = serializers.IntegerField(min_value=0, max_value=3650, default=7, write_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = TeamInviteToken
        fields = ["token", "url", "days", "created_at", "expires_at", "is_active"]
        read_only_fields = ["token", "created_at", "expires_at", "is_active"]

    def get_url(self, obj):
        return f"/join/{obj.token}/"
