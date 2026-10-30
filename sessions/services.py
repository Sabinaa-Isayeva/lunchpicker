"""Finalize sessions identically from the API and the scheduled worker."""
from django.db import transaction
from django.utils import timezone

from core.utils import audit, select_winning_proposal
from sessions.models import LunchSession, Notification, SelectionResult


@transaction.atomic
def finalize_session(session_id, actor=None):
    session = LunchSession.objects.select_for_update().select_related("team").get(pk=session_id)
    if session.end_time > timezone.now():
        raise ValueError("Session has not ended yet.")
    existing = SelectionResult.objects.filter(session=session).first()
    if existing:
        return existing, False
    winner, method = select_winning_proposal(session)
    if not winner:
        if session.is_recurring:
            session.create_next_occurrence()
        return None, False
    result = SelectionResult.objects.create(session=session, selected_proposal=winner, method_used=method)
    Notification.objects.bulk_create([
        Notification(recipient=member, session=session,
                     message=f"'{session.title}' üçün yer seçildi: {winner.restaurant.name}"[:255])
        for member in session.team.members.all()
    ])
    audit("session.result", actor, f"session_id={session.pk} proposal_id={winner.pk} method={method}")
    if session.is_recurring:
        session.create_next_occurrence()
    return result, True
