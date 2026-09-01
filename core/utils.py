import logging
import random

from django.db.models import Count

from sessions.models import LunchSession, SessionProposal

audit_logger = logging.getLogger("lunchpicker.audit")


def audit(action, user, detail=""):
    username = getattr(user, "username", "anonymous")
    audit_logger.info("action=%s user=%s %s", action, username, detail)


SELECTION_METHODS = LunchSession.SelectionAlgorithm.values


def select_winning_proposal(session):
    proposals = list(
        SessionProposal.objects.filter(session=session)
        .annotate(vote_count=Count("votes"))
    )
    if not proposals:
        return None, None

    method = session.selection_algorithm

    if method == LunchSession.SelectionAlgorithm.RANDOM:
        winner = random.choice(proposals)
    elif method == LunchSession.SelectionAlgorithm.WEIGHTED:
        weights = [p.vote_count + 1 for p in proposals]
        winner = random.choices(proposals, weights=weights, k=1)[0]
    else:
        top_votes = max(p.vote_count for p in proposals)
        tied = [p for p in proposals if p.vote_count == top_votes]
        winner = tied[0] if len(tied) == 1 else random.choice(tied)

    return winner, method
