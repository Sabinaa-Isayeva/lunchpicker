import pytest

from sessions.models import SelectionResult, Suggestion

from tests.conftest import auth, make_session_proposal

pytestmark = [pytest.mark.django_db]


def _ticket(api, session, restaurant_id):
    return api.post(
        f"/api/sessions/{session.pk}/suggestions/",
        {"restaurant": restaurant_id, "note": "please"},
    )


def test_ticket_flow_pending_then_approved(api, owner, member, team, restaurant, session):
    auth(api, member)
    res = _ticket(api, session, restaurant.pk)
    assert res.status_code == 201
    ticket = Suggestion.objects.get(pk=res.data["id"])
    assert ticket.status == Suggestion.Status.PENDING

    # not a proposal yet
    assert session.proposals.count() == 0

    # member cannot approve
    assert api.post(f"/api/suggestions/{ticket.pk}/approve/").status_code == 403

    # admin approves -> becomes votable proposal
    auth(api, owner)
    res = api.post(f"/api/suggestions/{ticket.pk}/approve/")
    assert res.status_code == 201
    ticket.refresh_from_db()
    assert ticket.status == Suggestion.Status.APPROVED
    assert session.proposals.filter(restaurant=restaurant).exists()

    # double approve fails
    assert api.post(f"/api/suggestions/{ticket.pk}/approve/").status_code == 400


def test_reject_with_admin_note(api, owner, member, team, restaurant, session):
    auth(api, member)
    res = _ticket(api, session, restaurant.pk)
    tid = res.data["id"]

    auth(api, owner)
    res = api.post(f"/api/suggestions/{tid}/reject/", {"admin_note": "baglidir"})
    assert res.status_code == 200
    ticket = Suggestion.objects.get(pk=tid)
    assert ticket.status == Suggestion.Status.REJECTED
    assert ticket.admin_note == "baglidir"
    assert session.proposals.count() == 0


def test_duplicate_restaurant_ticket_auto_rejected_on_approve(api, owner, member, team, restaurant, session):
    from tests.conftest import make_session_proposal

    make_session_proposal(session, restaurant, proposer=owner)
    auth(api, member)
    res = _ticket(api, session, restaurant.pk)  # creation allowed...
    assert res.status_code == 201
    tid = res.data["id"]

    auth(api, owner)
    res = api.post(f"/api/suggestions/{tid}/approve/")  # ...but approval is refused
    assert res.status_code == 400
    ticket = Suggestion.objects.get(pk=tid)
    assert ticket.status == Suggestion.Status.REJECTED


def test_guest_cannot_submit_ticket(api, guest, team, restaurant, session):
    auth(api, guest)
    assert _ticket(api, session, restaurant.pk).status_code == 400


def test_users_see_only_own_tickets(api, owner, member, team, restaurant, session):
    from tests.conftest import make_user

    other_user = make_user("other_member")
    from tests.conftest import add_member

    add_member(team, other_user)

    auth(api, member)
    _ticket(api, session, restaurant.pk)

    auth(api, other_user)
    r2 = _ticket(api, session, restaurant.pk)

    visible = api.get(f"/api/sessions/{session.pk}/suggestions/").data
    assert len(visible) == 1 and visible[0]["id"] == r2.data["id"]
