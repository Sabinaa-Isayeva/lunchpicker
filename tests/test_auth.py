import logging

import pytest

from tests.conftest import auth

pytestmark = [pytest.mark.django_db]


def test_jwt_login(api, owner):
    res = api.post("/api/auth/token/", {"username": "owner", "password": "pass12345!"})
    assert res.status_code == 200
    assert "access" in res.data and "refresh" in res.data

    bad = api.post("/api/auth/token/", {"username": "owner", "password": "wrong"})
    assert bad.status_code == 401


def test_signup_open_then_me(api):
    res = api.post("/api/users/", {"username": "fresh", "password": "fresh12345", "email": "f@f.local"})
    assert res.status_code == 201
    assert res.data["is_staff"] is False

    tokens = api.post("/api/auth/token/", {"username": "fresh", "password": "fresh12345"}).data
    api.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
    me = api.get("/api/users/me/")
    assert me.status_code == 200 and me.data["username"] == "fresh"


def test_non_staff_cannot_list_other_users(api, owner, member, team):
    auth(api, member)
    users = api.get("/api/users/?search=owner").data
    results = users["results"] if isinstance(users, dict) else users
    assert all(u["username"] != owner.username for u in results)


def test_unauthenticated_requests_rejected(api, team):
    assert api.get("/api/sessions/").status_code == 401
    assert api.get("/api/restaurants/").status_code == 401


def test_audit_util_logs(caplog):
    from django.contrib.auth import get_user_model

    from core.utils import audit

    User = get_user_model()
    user = User(username="audited")
    logger = logging.getLogger("lunchpicker.audit")
    # the audit logger has propagate=False, so attach caplog's handler directly
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="lunchpicker.audit"):
            audit("vote.create", user, "session_id=1 proposal_id=2 choice=3")
    finally:
        logger.removeHandler(caplog.handler)
    assert any(
        "action=vote.create" in r.getMessage() and "user=audited" in r.getMessage()
        for r in caplog.records
    )
