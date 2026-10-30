import logging
import random

from django.db.models import Count, Sum

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
        .annotate(vote_score=Sum("votes__choice"))
    )
    if not proposals:
        return None, None

    method = session.selection_algorithm

    if method == LunchSession.SelectionAlgorithm.RANDOM:
        winner = random.choice(proposals)
    elif method == LunchSession.SelectionAlgorithm.WEIGHTED:
        from core.models import SystemSettings
        base_weight = SystemSettings.current().weighted_base_weight
        weights = [((p.vote_score or 0) if session.voting_mode == "rating" else p.vote_count)
                   + base_weight for p in proposals]
        winner = random.choices(proposals, weights=weights, k=1)[0]
    else:
        def score(proposal):
            return (proposal.vote_score or 0) if session.voting_mode == "rating" else proposal.vote_count
        top_votes = max(score(p) for p in proposals)
        tied = [p for p in proposals if score(p) == top_votes]
        winner = tied[0] if len(tied) == 1 else random.choice(tied)

    return winner, method
