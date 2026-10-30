import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from restaurants.models import MenuItem, Restaurant
from sessions.models import LunchSession
from teams.models import Membership, Team

User = get_user_model()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from django.core.cache import cache
    cache.clear()


def make_user(username, **extra):
    defaults = {"email": f"{username}@test.local", "password": "pass12345!"}
    defaults.update(extra)
    return User.objects.create_user(username=username, **defaults)


def make_team(owner, name="Office Squad", with_members=True):
    team = Team.objects.create(name=name, created_by=owner)
    Membership.objects.create(team=team, user=owner, role=Membership.Role.OWNER)
    return team


def add_member(team, user, role=Membership.Role.MEMBER):
    # the Membership row IS the M2M through row; creating it adds the member
    return Membership.objects.get_or_create(team=team, user=user, defaults={"role": role})[0]


def make_restaurant(name="Test Kebap", cuisine="turkish", price=12.50):
    return Restaurant.objects.create(
        name=name, address="Somewhere 1", cuisine_type=cuisine, average_price=price,
    )


def make_menu_item(restaurant, name="Adana", price=10):
    return MenuItem.objects.create(restaurant=restaurant, name=name, price=price)


def make_session(team, creator, active=True, recurring=False, rule="", algorithm="majority"):
    from django.utils import timezone

    now = timezone.now()
    start = now - timezone.timedelta(hours=1) if active else now - timezone.timedelta(days=3)
    end = now + timezone.timedelta(hours=1) if active else now - timezone.timedelta(days=2)
    return LunchSession.objects.create(
        team=team, title="Cume Nahari", start_time=start, end_time=end,
        is_recurring=recurring, recurrence_rule=rule,
        selection_algorithm=algorithm, created_by=creator,
    )


def make_session_proposal(session, restaurant, proposer):
    from sessions.models import SessionProposal

    return SessionProposal.objects.create(session=session, restaurant=restaurant, proposer=proposer)


def distinct_restaurants(n, prefix="Spot"):
    return [make_restaurant(name=f"{prefix} {i}", cuisine="european") for i in range(n)]


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def owner():
    return make_user("owner")


@pytest.fixture
def member():
    return make_user("member")


@pytest.fixture
def guest():
    return make_user("guest")


@pytest.fixture
def outsider():
    return make_user("outsider")


@pytest.fixture
def team(owner, member, guest):
    team = make_team(owner)
    add_member(team, member)
    add_member(team, guest, Membership.Role.GUEST)
    return team


@pytest.fixture
def restaurant():
    return make_restaurant()


@pytest.fixture
def session(team, owner):
    return make_session(team, owner, active=True)


def auth(api, user):
    api.force_authenticate(user=user)
    return api


def get_tokens(client, username, password="pass12345!"):
    res = client.post("/api/auth/token/", {"username": username, "password": password})
    return res.data["access"], res.data["refresh"]
