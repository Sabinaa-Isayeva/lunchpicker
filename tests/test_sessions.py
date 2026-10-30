import pytest
from django.utils import timezone

from sessions.models import LunchSession, Vote

from tests.conftest import auth, make_session, make_session_proposal

pytestmark = [pytest.mark.django_db]


def _vote(api, session, proposal, **overrides):
    pid = proposal if isinstance(proposal, int) else proposal.pk
    payload = {"proposal": pid, "choice": 1}
    payload.update(overrides)
    return api.post(f"/api/sessions/{session.pk}/votes/", payload)


def test_member_can_vote_and_update(api, owner, member, team, restaurant, session):
    auth(api, member)
    res = api.post(f"/api/sessions/{session.pk}/proposals/", {"restaurant": restaurant.pk})
    assert res.status_code == 201
    proposal = res.data["id"]

    res = _vote(api, session, proposal)
    assert res.status_code == 201

    res = _vote(api, session, proposal, choice=5)
    assert res.status_code == 200
    assert res.data["choice"] == 5
    assert Vote.objects.filter(session=session).count() == 1


def test_duplicate_vote_rejected(api, owner, member, team, restaurant, session):
    from tests.conftest import distinct_restaurants

    other = distinct_restaurants(1)[0]
    p1 = make_session_proposal(session, restaurant, proposer=owner)
    p2 = make_session_proposal(session, other, proposer=owner)

    auth(api, member)
    assert _vote(api, session, p1).status_code == 201
    # re-voting the same proposal UPDATES the rating (spec: cast or modify votes)
    res = _vote(api, session, p1, choice=4)
    assert res.status_code == 200
    assert res.data["choice"] == 4
    assert Vote.objects.filter(session=session, voter=member).count() == 1
    # other proposals still votable
    assert _vote(api, session, p2).status_code == 201


def test_guest_cannot_vote_or_propose(api, guest, owner, team, restaurant, session):
    auth(api, guest)
    res = api.post(f"/api/sessions/{session.pk}/proposals/", {"restaurant": restaurant.pk})
    assert res.status_code == 400
    assert "read-only" in str(res.data)

    proposal = make_session_proposal(session, restaurant, proposer=owner)
    res = _vote(api, session, proposal)
    assert res.status_code == 400


def test_vote_rate_limit(api, owner, member, team, session):
    from tests.conftest import distinct_restaurants

    restaurants = distinct_restaurants(6)
    proposals = [make_session_proposal(session, r, proposer=owner) for r in restaurants]

    auth(api, member)
    codes = [_vote(api, session, p).status_code for p in proposals]
    assert codes[:5] == [201] * 5
    assert codes[5] == 429


def test_outsider_cannot_vote(api, outsider, owner, team, restaurant, session):
    proposal = make_session_proposal(session, restaurant, proposer=owner)
    auth(api, outsider)
    assert _vote(api, session, proposal).status_code in (400, 403, 404)


def test_vote_requires_active_session(api, member, owner, team, restaurant):
    closed = make_session(team, owner, active=False)
    proposal = make_session_proposal(closed, restaurant, proposer=owner)
    auth(api, member)
    assert _vote(api, closed, proposal).status_code == 400
import pytest
from django.utils import timezone

from sessions.models import LunchSession, Notification, SelectionResult, Vote


def test_selection_majority_notifies_and_creates_history(api, owner, member, team, restaurant, session):
    from tests.conftest import auth, make_restaurant

    r2 = make_restaurant(name="Other House", cuisine="national")
    p1 = make_session_proposal(session, restaurant, proposer=owner)
    p2 = make_session_proposal(session, r2, proposer=owner)

    auth(api, owner)
    Vote.objects.create(session=session, voter=member, proposal=p1)
    Vote.objects.create(session=session, voter=owner, proposal=p1)
    Vote.objects.create(session=session, voter=owner, proposal=p2)

    LunchSession.objects.filter(pk=session.pk).update(
        end_time=timezone.now() - timezone.timedelta(minutes=1)
    )

    res = api.post(f"/api/sessions/{session.pk}/result/")
    assert res.status_code == 201
    result = SelectionResult.objects.get(session=session)
    assert result.selected_proposal == p1

    assert Notification.objects.filter(recipient=member).exists()
    assert Notification.objects.filter(recipient=owner).exists()
    assert not session.next_occurrences.exists()


def test_recurring_session_spawns_next_occurrence(api, owner, team, restaurant, session):
    from tests.conftest import auth

    LunchSession.objects.filter(pk=session.pk).update(
        is_recurring=True,
        recurrence_rule="weekly",
        end_time=timezone.now() - timezone.timedelta(minutes=5),
    )
    make_session_proposal(session, restaurant, proposer=owner)
    session.refresh_from_db()

    auth(api, owner)
    assert api.post(f"/api/sessions/{session.pk}/result/").status_code == 201
    child = session.next_occurrences.first()
    assert child is not None
    assert child.is_recurring and child.recurrence_rule == "weekly"
    assert child.start_time > session.start_time


def test_process_recurring_command(api, owner, team):
    from django.core.management import call_command

    ended = make_session(team, owner, active=False, recurring=True, rule="daily")
    call_command("process_recurring")
    child = ended.next_occurrences.first()
    assert child is not None
    assert child.recurrence_rule == "daily"

    # idempotent: running again does not duplicate
    call_command("process_recurring")
    assert ended.next_occurrences.count() == 1
