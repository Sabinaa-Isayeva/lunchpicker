from datetime import date
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets

from analytics.serializers import LunchHistorySerializer
from sessions.models import LunchSession, SelectionResult, Vote
from teams.models import Team
from restaurants.models import Restaurant


class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _date_range(self, request, field="start_time"):
        filters = {}
        parsed = {}
        for param, lookup in (("start", "gte"), ("end", "lte")):
            value = request.query_params.get(param)
            if value:
                try:
                    parsed[param] = date.fromisoformat(value)
                except ValueError:
                    raise ValidationError({param: "Use an ISO date (YYYY-MM-DD)."})
                filters[f"{field}__date__{lookup}"] = parsed[param]
        if len(parsed) == 2 and parsed["start"] > parsed["end"]:
            raise ValidationError({"end": "End date must be on or after start date."})
        return filters

    def _team(self, request, team_id):
        team = get_object_or_404(Team, pk=team_id)
        if not (request.user.is_staff or team.members.filter(pk=request.user.pk).exists()):
            raise PermissionDenied("You must be a member of this team.")
        return team

    @action(detail=False, methods=["get"], url_path="team/(?P<team_id>\\d+)", url_name="team")
    def team(self, request, team_id=None):
        self._team(request, team_id)
        sessions = LunchSession.objects.filter(team_id=team_id, **self._date_range(request))
        results = SelectionResult.objects.filter(session__in=sessions).select_related("selected_proposal__restaurant")

        by_restaurant = (
            results.values("selected_proposal__restaurant__name")
            .annotate(wins=Count("id"))
            .order_by("-wins")
        )
        by_cuisine = (
            results.values("selected_proposal__restaurant__cuisine_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        participation = (
            Vote.objects.filter(session__in=sessions, session__is_anonymous=False)
            .values("voter__username")
            .annotate(votes_cast=Count("id"))
            .order_by("-votes_cast")
        )

        return Response({
            "team": int(team_id),
            "total_sessions": sessions.count(),
            "closed_sessions_with_result": results.count(),
            "avg_votes_per_session": round(
                Vote.objects.filter(session__in=sessions).count() / max(sessions.count(), 1), 2
            ),
            "wins_by_restaurant": list(by_restaurant),
            "wins_by_cuisine": list(by_cuisine),
            "participation": list(participation),
        })

    def _history_queryset(self, request, **filters):
        qs = SelectionResult.objects.select_related(
            "session__team", "selected_proposal__restaurant"
        )
        qs = qs.filter(**self._date_range(request, "session__end_time"))
        venue = request.query_params.get("restaurant") or request.query_params.get("venue")
        if venue:
            if venue.isdigit():
                qs = qs.filter(selected_proposal__restaurant_id=int(venue))
            else:
                qs = qs.filter(selected_proposal__restaurant__name__icontains=venue)
        return qs.filter(**filters).order_by("-executed_at")

    @action(detail=False, methods=["get"], url_path="history/team/(?P<team_id>\\d+)", url_name="history-team")
    def history_team(self, request, team_id=None):
        self._team(request, team_id)
        data = LunchHistorySerializer(
            self._history_queryset(request, session__team_id=team_id), many=True
        ).data
        return Response(data)

    @action(detail=False, methods=["get"], url_path="history/me", url_name="history-me")
    def history_me(self, request):
        user = request.user
        qs = self._history_queryset(request)
        qs = qs.filter(session__votes__voter=user) | qs.filter(session__created_by=user)
        return Response(LunchHistorySerializer(qs.distinct(), many=True).data)

    @action(detail=False, methods=["get"], url_path="system")
    def system(self, request):
        if not request.user.is_staff:
            raise PermissionDenied("Administrator access is required.")
        User = get_user_model()
        return Response({
            "users": User.objects.count(), "active_users": User.objects.filter(is_active=True).count(),
            "teams": Team.objects.count(), "restaurants": Restaurant.objects.count(),
            "sessions": LunchSession.objects.count(), "results": SelectionResult.objects.count(),
            "votes": Vote.objects.count(),
        })
