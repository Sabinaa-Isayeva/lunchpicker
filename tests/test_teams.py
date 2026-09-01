import pytest

from teams.models import Membership, Team, TeamInviteToken

pytestmark = [pytest.mark.django_db]


def test_owner_created_as_member_on_team_create(api, owner):
    from tests.conftest import auth

    auth(api, owner)
    res = api.post("/api/teams/", {"name": "Squad A", "description": ""})
    assert res.status_code == 201
    team = Team.objects.get(name="Squad A")
    assert team.members.filter(pk=owner.pk).exists()
    assert team.memberships.get(user=owner).role == Membership.Role.OWNER


def test_duplicate_team_name_rejected(api, owner):
    from tests.conftest import auth, make_team

    make_team(owner, name="Unique Crew")
    auth(api, owner)
    res = api.post("/api/teams/", {"name": "unique crew"})
    assert res.status_code == 400


def test_non_owner_cannot_update_team(api, owner, member, team):
    from tests.conftest import auth

    auth(api, member)
    res = api.patch(f"/api/teams/{team.pk}/", {"name": "Hijacked"})
    assert res.status_code == 403


def test_invite_link_flow(api, owner, member, outsider, team):
    from tests.conftest import add_member, auth

    # only the owner can generate a link
    auth(api, member)
    assert api.post(f"/api/teams/{team.pk}/invite_link/").status_code == 403

    auth(api, owner)
    res = api.post(f"/api/teams/{team.pk}/invite_link/")
    assert res.status_code == 201
    token = res.data["token"]
    assert TeamInviteToken.objects.filter(token=token).exists()

    # outsider previews then joins
    auth(api, outsider)
    preview = api.get(f"/api/join/{token}/preview/")
    assert preview.status_code == 200
    assert preview.data["team_name"] == team.name

    join = api.post(f"/api/join/{token}/")
    assert join.status_code == 201
    assert team.members.filter(pk=outsider.pk).exists()

    # joining twice is idempotent
    again = api.post(f"/api/join/{token}/")
    assert again.status_code == 200


def test_expired_invite_rejected(api, owner, outsider, team):
    from datetime import timedelta

    from django.utils import timezone

    from tests.conftest import auth

    token = TeamInviteToken.objects.create(
        team=team, created_by=owner,
        expires_at=timezone.now() - timedelta(days=1),
    )
    auth(api, outsider)
    assert api.get(f"/api/join/{token.token}/preview/").status_code == 404
    assert api.post(f"/api/join/{token.token}/").status_code == 404


def test_owner_cannot_be_removed(api, owner, team):
    from tests.conftest import auth

    auth(api, owner)
    res = api.delete(f"/api/teams/{team.pk}/members/?username={owner.username}")
    assert res.status_code == 400
