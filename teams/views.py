import uuid

from django.contrib.auth import get_user_model
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
from teams.serializers import InviteSerializer, MembershipSerializer, TeamSerializer


class TeamViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [IsTeamOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Team.objects.all()
        return Team.objects.filter(members=user)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            self.permission_classes = []
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsTeamOwner])
    def invite_link(self, request, pk=None):
        team = self.get_object()
        days = int(request.data.get("days", 7))
        token = TeamInviteToken.objects.create(
            team=team,
            created_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=days) if days else None,
        )
        audit("team.invite_link", request.user, f"team_id={team.pk}")
        return Response({
            "token": str(token.token),
            "url": f"/join/{token.token}/",
            "expires_at": token.expires_at,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post", "delete"], url_path="members")
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
                team.members.add(user)
                serializer = MembershipSerializer(membership)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response({"detail": "User is already a member."}, status=status.HTTP_400_BAD_REQUEST)

        username = request.query_params.get("username")
        if not username:
            return Response({"detail": "Provide ?username= to remove a member."}, status=status.HTTP_400_BAD_REQUEST)
        membership = get_object_or_404(team.memberships, user__username=username)
        if membership.user_id == team.created_by_id:
            return Response({"detail": "The team owner cannot be removed."}, status=status.HTTP_400_BAD_REQUEST)
        team.members.remove(membership.user)
        membership.delete()
        audit("team.member_remove", request.user, f"team_id={team.pk} username={username}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class JoinTeamView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_token(self, token):
        invite = get_object_or_404(
            TeamInviteToken.objects.select_related("team"), token=token, is_active=True
        )
        if invite.expires_at and invite.expires_at < timezone.now():
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

    def post(self, request, token):
        invite = self._get_token(token)
        if not invite:
            return Response({"detail": "Bu dəvət linki etibarsızdır."}, status=404)
        membership, created = Membership.objects.get_or_create(
            team=invite.team,
            user=request.user,
            defaults={"role": Membership.Role.MEMBER},
        )
        if created:
            invite.team.members.add(request.user)
            audit("team.join", request.user, f"team_id={invite.team.pk} via_invite")
        serializer = MembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class JoinTeamPreviewView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        invite = TeamInviteToken.objects.filter(token=token, is_active=True).select_related("team").first()
        if not invite or (invite.expires_at and invite.expires_at < timezone.now()):
            return Response({"detail": "Bu dəvət linki etibarsızdır."}, status=404)
        return Response({"team_name": invite.team.name})
