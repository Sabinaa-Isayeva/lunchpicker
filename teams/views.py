import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsTeamOwner, is_team_owner
from core.utils import audit
from teams.models import Membership, Team, TeamInviteToken
from teams.serializers import InviteLinkSerializer, InviteSerializer, MembershipSerializer, TeamSerializer


class TeamViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [IsTeamOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Team.objects.all()
        return Team.objects.filter(members=user)

    def get_permissions(self):
        if self.action in ("list", "retrieve", "members"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsTeamOwner()]

    def perform_create(self, serializer):
        with transaction.atomic():
            team = serializer.save(created_by=self.request.user)
        audit("team.create", self.request.user, f"team_id={team.pk}")

    def perform_update(self, serializer):
        team = serializer.save()
        audit("team.update", self.request.user, f"team_id={team.pk}")

    def perform_destroy(self, instance):
        audit("team.delete", self.request.user, f"team_id={instance.pk}")
        instance.delete()

    @action(detail=True, methods=["get", "post"], permission_classes=[IsTeamOwner])
    def invite_link(self, request, pk=None):
        team = self.get_object()
        if request.method == "GET":
            tokens = team.invite_tokens.order_by("-created_at")
            return Response(InviteLinkSerializer(tokens, many=True).data)
        serializer = InviteLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]
        token = TeamInviteToken.objects.create(
            team=team,
            created_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=days) if days else None,
        )
        audit("team.invite_link", request.user, f"team_id={team.pk}")
        return Response(InviteLinkSerializer(token).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"invite_links/(?P<token>[0-9a-fA-F-]{36})")
    def revoke_invite(self, request, pk=None, token=None):
        try:
            token = uuid.UUID(token)
        except ValueError:
            return Response({"detail": "Invalid invite token."}, status=400)
        invite = get_object_or_404(self.get_object().invite_tokens, token=token)
        invite.is_active = False
        invite.save(update_fields=["is_active"])
        audit("team.invite_revoke", request.user, f"team_id={invite.team_id}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post", "patch", "delete"], url_path="members")
    @transaction.atomic
    def members(self, request, pk=None):
        team = self.get_object()

        if request.method == "GET":
            memberships = team.memberships.select_related("user")
            return Response(MembershipSerializer(memberships, many=True).data)

        if not (request.user.is_staff or is_team_owner(request.user, team)):
            return Response({"detail": "Only the team owner can manage members."}, status=status.HTTP_403_FORBIDDEN)

        if request.method == "POST":
            invite = InviteSerializer(data=request.data)
            invite.is_valid(raise_exception=True)
            User = get_user_model()
            user = User.objects.get(username=invite.validated_data["username"])
            membership, created = Membership.objects.get_or_create(
                team=team,
                user=user,
                defaults={"role": invite.validated_data["role"]},
            )
            if created:
                audit("team.member_add", request.user, f"team_id={team.pk} username={user.username}")
                serializer = MembershipSerializer(membership)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response({"detail": "User is already a member."}, status=status.HTTP_400_BAD_REQUEST)

        username = request.data.get("username") or request.query_params.get("username")
        if not username:
            return Response({"detail": "Provide ?username= to remove a member."}, status=status.HTTP_400_BAD_REQUEST)
        membership = get_object_or_404(team.memberships, user__username=username)
        if membership.user_id == team.created_by_id:
            return Response({"detail": "The founding owner's membership cannot be changed."}, status=status.HTTP_400_BAD_REQUEST)
        if request.method == "PATCH":
            serializer = MembershipSerializer(membership, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit("team.member_role", request.user, f"team_id={team.pk} username={username}")
            return Response(serializer.data)
        membership.delete()
        audit("team.member_remove", request.user, f"team_id={team.pk} username={username}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_token(self, token, lock=False):
        tokens = TeamInviteToken.objects.select_related("team")
        if lock:
            tokens = tokens.select_for_update()
        invite = get_object_or_404(
            tokens, token=token, is_active=True
        )
        if invite.expires_at and invite.expires_at <= timezone.now():
            return None
        return invite

    def get(self, request, token):
        invite = self._get_token(token)
        if not invite:
            return Response({"detail": "Bu dəvət linki etibarsızdır."}, status=404)
        already = Membership.objects.filter(team=invite.team, user=request.user).exists()
        return Response({
            "team": TeamSerializer(invite.team, context={"request": request}).data,
            "already_member": already,
        })

    @transaction.atomic
    def post(self, request, token):
        invite = self._get_token(token, lock=True)
        if not invite:
            return Response({"detail": "Bu dəvət linki etibarsızdır."}, status=404)
        membership, created = Membership.objects.get_or_create(
            team=invite.team,
            user=request.user,
            defaults={"role": Membership.Role.MEMBER},
        )
        if created:
            audit("team.join", request.user, f"team_id={invite.team.pk} via_invite")
        serializer = MembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class JoinTeamPreviewView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        invite = TeamInviteToken.objects.filter(token=token, is_active=True).select_related("team").first()
        if not invite or (invite.expires_at and invite.expires_at <= timezone.now()):
            return Response({"detail": "Bu dəvət linki etibarsızdır."}, status=404)
        return Response({"team_name": invite.team.name})
