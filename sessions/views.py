from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import is_team_owner
from core.utils import audit, select_winning_proposal
from sessions.models import LunchSession, Notification, SelectionResult, SessionProposal, Suggestion, Vote
from sessions.serializers import (
    LunchSessionSerializer,
    NotificationSerializer,
    SelectionResultSerializer,
    SessionProposalSerializer,
    SuggestionSerializer,
    VoteSerializer,
)


class LunchSessionViewSet(viewsets.ModelViewSet):
    serializer_class = LunchSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["team", "selection_algorithm", "is_recurring"]
    search_fields = ["title"]
    ordering_fields = ["start_time", "end_time", "created_at"]

    def _payload(self, extra=None):
        data = self.request.data
        if hasattr(data, "dict"):
            data = {k: v for k, v in data.items()}
        else:
            data = dict(data)
        if extra:
            data.update(extra)
        return data

    def get_queryset(self):
        user = self.request.user
        qs = LunchSession.objects.select_related("team").prefetch_related("proposals")
        if user.is_staff:
            return qs
        return qs.filter(team__members=user)

    def perform_create(self, serializer):
        session = serializer.save()
        audit("session.create", self.request.user, f"session_id={session.pk} title='{session.title}'")

    @action(detail=True, methods=["get", "post"], permission_classes=[IsAuthenticated])
    def proposals(self, request, pk=None):
        session = self.get_object()

        if request.method == "GET":
            data = SessionProposal.objects.filter(session=session).select_related("restaurant", "proposer")
            return Response(SessionProposalSerializer(data, many=True, context=self.get_serializer_context()).data)

        serializer = SessionProposalSerializer(
            data=self._payload({"session": session.pk}),
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        proposal = serializer.save()
        return Response(
            SessionProposalSerializer(proposal, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post", "put", "delete"])
    def votes(self, request, pk=None):
        session = self.get_object()

        if request.method == "GET":
            votes = Vote.objects.filter(session=session).select_related("voter", "proposal__restaurant")
            if not (request.user.is_staff or session.team.created_by_id == request.user.pk):
                votes = votes.filter(voter=request.user)
            return Response(VoteSerializer(votes, many=True).data)

        if request.method == "DELETE":
            proposal_id = request.data.get("proposal") or request.query_params.get("proposal")
            if not proposal_id:
                return Response({"detail": "Provide 'proposal' id."}, status=400)
            deleted, _ = Vote.objects.filter(session=session, voter=request.user, proposal_id=proposal_id).delete()
            if not deleted:
                return Response({"detail": "No vote to remove."}, status=404)
            audit("vote.delete", request.user, f"session_id={session.pk} proposal_id={proposal_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)

        existing = Vote.objects.filter(
            session=session,
            voter=request.user,
            proposal_id=request.data.get("proposal"),
        ).first()
        if existing:
            serializer = VoteSerializer(
                existing,
                data=self._payload({
                    "choice": request.data.get("choice", existing.choice),
                    "session": session.pk,
                    "proposal": request.data.get("proposal"),
                }),
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            existing.refresh_from_db()
            audit("vote.update", request.user,
                  f"session_id={session.pk} proposal_id={existing.proposal_id} choice={existing.choice}")
            return Response(VoteSerializer(existing).data)

        serializer = VoteSerializer(
            data=self._payload({"session": session.pk}),
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        vote = serializer.save()
        audit("vote.create", request.user,
              f"session_id={session.pk} proposal_id={vote.proposal_id} choice={vote.choice}")
        return Response(VoteSerializer(vote).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def suggestions(self, request, pk=None):
        session = self.get_object()

        if request.method == "GET":
            tickets = Suggestion.objects.filter(session=session).select_related("user", "restaurant")
            if not (request.user.is_staff or session.team.created_by_id == request.user.pk):
                tickets = tickets.filter(user=request.user)
            return Response(SuggestionSerializer(tickets, many=True).data)

        serializer = SuggestionSerializer(
            data=self._payload({"session": session.pk}),
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        return Response(SuggestionSerializer(ticket).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def clone(self, request, pk=None):
        session = self.get_object()
        if not (request.user.is_staff or session.team.created_by_id == request.user.pk):
            return Response({"detail": "Only owner can clone."}, status=403)
        from django.utils import timezone as tz
        base = session
        new = LunchSession.objects.create(
            team=base.team,
            title=base.title + " (kopya)",
            start_time=tz.now() + tz.timedelta(hours=1),
            end_time=tz.now() + tz.timedelta(hours=3),
            is_recurring=base.is_recurring,
            recurrence_rule=base.recurrence_rule,
            selection_algorithm=base.selection_algorithm,
            is_anonymous=base.is_anonymous,
            voting_mode=base.voting_mode,
            is_announcement=base.is_announcement,
            created_by=request.user,
        )
        audit("session.clone", request.user, f"from={base.pk} to={new.pk}")
        return Response(LunchSessionSerializer(new).data, status=201)

    @action(detail=True, methods=["get", "post"])
    def result(self, request, pk=None):
        session = self.get_object()
        selection = SelectionResult.objects.filter(session=session).first()

        if request.method == "GET":
            if not selection:
                return Response({"detail": "No result yet. The session may still be running."}, status=404)
            return Response(SelectionResultSerializer(selection).data)

        if not (request.user.is_staff or session.team.created_by_id == request.user.pk):
            return Response({"detail": "Only the team owner can trigger the selection."}, status=403)
        if session.end_time > timezone.now():
            return Response({"detail": "Session has not ended yet."}, status=400)
        if selection:
            return Response(SelectionResultSerializer(selection).data)

        winner, method = select_winning_proposal(session)
        if not winner:
            return Response({"detail": "No proposals to select from."}, status=400)
        selection = SelectionResult.objects.create(
            session=session, selected_proposal=winner, method_used=method
        )

        restaurant_name = winner.restaurant.name
        for member in session.team.members.all():
            Notification.objects.create(
                recipient=member,
                session=session,
                message=f"'{session.title}' üçün yer seçildi: {restaurant_name}",
            )
        audit("session.result", request.user,
              f"session_id={session.pk} selected='{restaurant_name}' method={method}")

        if session.is_recurring:
            next_session = session.create_next_occurrence()
            if next_session:
                audit("session.recurring_spawn", request.user, f"new_session_id={next_session.pk}")

        return Response(SelectionResultSerializer(selection).data, status=201)


class SuggestionViewSet(viewsets.ModelViewSet):
    serializer_class = SuggestionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Suggestion.objects.select_related("user", "restaurant", "session")
        from teams.models import Team

        owned_team_ids = Team.objects.filter(created_by=user).values_list("id", flat=True)
        return Suggestion.objects.filter(
            Q(user=user) | Q(session__team_id__in=owned_team_ids)
        ).select_related("user", "restaurant", "session")

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Create suggestions via /api/sessions/{id}/suggestions/."}, status=405)

    def _can_moderate(self, user, ticket):
        if user.is_staff:
            return True
        return is_team_owner(user, ticket.session.team)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        ticket = self.get_object()
        if not self._can_moderate(request.user, ticket):
            return Response({"detail": "Only admins or the team owner can approve."}, status=403)
        if ticket.status != Suggestion.Status.PENDING:
            return Response({"detail": f"Ticket is already {ticket.status}."}, status=400)

        if SessionProposal.objects.filter(session=ticket.session, restaurant=ticket.restaurant).exists():
            ticket.status = Suggestion.Status.REJECTED
            ticket.admin_note = "Bu restoran sessiyada artıq təklif edilib."
            ticket.save()
            return Response({"detail": "Restaurant already proposed; ticket rejected."}, status=400)

        proposal = SessionProposal.objects.create(
            session=ticket.session,
            restaurant=ticket.restaurant,
            proposer=ticket.user,
        )
        proposal.menu_items.set(ticket.menu_items.all())
        ticket.status = Suggestion.Status.APPROVED
        ticket.save()
        audit("suggestion.approve", request.user, f"suggestion_id={ticket.pk}")
        return Response({
            "ticket": SuggestionSerializer(ticket).data,
            "proposal": SessionProposalSerializer(proposal, context=self.get_serializer_context()).data,
        }, status=201)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        ticket = self.get_object()
        if not self._can_moderate(request.user, ticket):
            return Response({"detail": "Only admins or the team owner can reject."}, status=403)
        if ticket.status != Suggestion.Status.PENDING:
            return Response({"detail": f"Ticket is already {ticket.status}."}, status=400)
        ticket.status = Suggestion.Status.REJECTED
        ticket.admin_note = request.data.get("admin_note", "")[:255]
        ticket.save()
        audit("suggestion.reject", request.user, f"suggestion_id={ticket.pk}")
        return Response(SuggestionSerializer(ticket).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=["get"])
    def unread(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread": count})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"marked_read": updated})
