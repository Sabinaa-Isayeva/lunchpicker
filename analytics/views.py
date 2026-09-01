from django.db.models import Count
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets

from analytics.serializers import LunchHistorySerializer
from sessions.models import LunchSession, SelectionResult, Vote


class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _date_range(self, request):
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        qs = {}
        if start:
            qs["start__gte"] = start
        if end:
            qs["start__lte"] = end
        return qs

    @action(detail=False, methods=["get"], url_path="team/(?P<team_id>\\d+)", url_name="team")
    def team(self, request, team_id=None):
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
            Vote.objects.filter(session__in=sessions)
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
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start:
            qs = qs.filter(session__end_time__gte=start)
        if end:
            qs = qs.filter(session__end_time__lte=end)
        venue = request.query_params.get("restaurant") or request.query_params.get("venue")
        if venue:
            if venue.isdigit():
                qs = qs.filter(selected_proposal__restaurant_id=int(venue))
            else:
                qs = qs.filter(selected_proposal__restaurant__name__icontains=venue)
        return qs.filter(**filters).order_by("-executed_at")

    @action(detail=False, methods=["get"], url_path="history/team/(?P<team_id>\\d+)", url_name="history-team")
    def history_team(self, request, team_id=None):
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
