import pytest
from django.utils import timezone

from sessions.models import LunchSession, Notification, SelectionResult, Vote

from tests.conftest import auth, make_session_proposal

pytestmark = [pytest.mark.django_db]


def test_team_history_with_filters(api, owner, member, team, restaurant):
    from django.utils import timezone

    from tests.conftest import make_restaurant, make_session

    r2 = make_restaurant(name="History House", cuisine="asian")

    for name, rest in [("Week 1", restaurant), ("Week 2", r2)]:
        s = make_session(team, owner, active=False)
        LunchSession.objects.filter(pk=s.pk).update(
            title=name,
            start_time=timezone.now() - timezone.timedelta(days=7),
            end_time=timezone.now() - timezone.timedelta(days=6),
        )
        s.refresh_from_db()
        SelectionResult.objects.create(
            session=s, selected_proposal=make_session_proposal(s, rest, proposer=owner),
            method_used="majority",
        )

    auth(api, owner)
    res = api.get(f"/api/analytics/history/team/{team.pk}/")
    assert res.status_code == 200
    items = res.data["results"] if isinstance(res.data, dict) else res.data
    assert len(items) == 2

    res = api.get(f"/api/analytics/history/team/{team.pk}/?restaurant=History")
    items = res.data["results"] if isinstance(res.data, dict) else res.data
    assert len(items) == 1 and items[0]["restaurant_name"] == "History House"

    cutoff = (timezone.now() - timezone.timedelta(days=3)).date().isoformat()
    res = api.get(f"/api/analytics/history/team/{team.pk}/?start={cutoff}")
    items = res.data["results"] if isinstance(res.data, dict) else res.data
    assert len(items) == 0


def test_my_history(api, owner, member, team, restaurant, session):
    session.end_time = timezone.now() - timezone.timedelta(hours=1)
    LunchSession.objects.filter(pk=session.pk).update(end_time=session.end_time)
    result = SelectionResult.objects.create(
        session=session,
        selected_proposal=make_session_proposal(session, restaurant, proposer=owner),
        method_used="majority",
    )
    Vote.objects.create(session=session, voter=member, proposal=result.selected_proposal)

    auth(api, member)
    names = [h["restaurant_name"] for h in api.get("/api/analytics/history/me/").data]
    assert names == [restaurant.name]

    from tests.conftest import make_user

    stranger = make_user("stranger")
    auth(api, stranger)
    assert api.get("/api/analytics/history/me/").data == []


def test_notifications_flow(api, owner, member, team, restaurant):
    Notification.objects.create(recipient=member, message="Yer secildi: Dolma House")
    Notification.objects.create(recipient=member, message="Ikinci bildiris", is_read=True)

    auth(api, member)
    unread = api.get("/api/notifications/unread/")
    assert unread.data["unread"] == 1

    raw = api.get("/api/notifications/").data
    first = next(item for item in (raw["results"] if isinstance(raw, dict) else raw) if not item["is_read"])
    assert api.post(f"/api/notifications/{first['id']}/read/").status_code == 200
    assert api.get("/api/notifications/unread/").data["unread"] == 0

    Notification.objects.create(recipient=member, message="Yeni")
    assert api.post("/api/notifications/read_all/").data["marked_read"] == 1

    auth(api, owner)
    raw = api.get("/api/notifications/").data
    items = raw["results"] if isinstance(raw, dict) else raw
    assert all(n["message"] != "Yeni" for n in items)
