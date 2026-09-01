from rest_framework.permissions import BasePermission


def is_team_owner(user, team):
    return team.created_by_id == user.pk


def is_team_member(user, team):
    return team.members.filter(pk=user.pk).exists()


class IsTeamOwner(BasePermission):
    message = "Only the team owner (or an admin) can perform this action."

    def has_object_permission(self, request, view, obj):
        team = obj if hasattr(obj, "created_by") else obj.team
        return is_team_owner(request.user, team) or request.user.is_staff


class IsTeamMember(BasePermission):
    message = "You must be a member of this team."

    def has_object_permission(self, request, view, obj):
        team = obj if hasattr(obj, "members") else obj.session.team
        return is_team_member(request.user, team) or request.user.is_staff


class IsAdminUserOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)
