"""Regression coverage for the missing PDF workflows and access boundaries."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from core.models import SystemSettings
from core.utils import select_winning_proposal
from sessions.models import LunchSession, Notification, SelectionResult, Vote
from sessions.services import finalize_session
from teams.models import Membership, Team
from tests.conftest import (add_member, auth, make_menu_item, make_restaurant,
                            make_session, make_session_proposal, make_team, make_user)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('url', ['/api/teams/', '/api/users/me/', '/api/settings/'])
def test_private_endpoints_require_login(api, url):
    assert api.get(url).status_code == 401


def test_signup_does_not_join_existing_private_team(api, owner):
    team = make_team(owner, name='Office Squad')
    response = api.post('/api/users/', {'username': 'newcomer', 'email': 'new@test.local', 'password': 'safe-and-long-938!'})
    assert response.status_code == 201
    assert not team.members.filter(pk=response.data['id']).exists()


@pytest.mark.parametrize('password', [None, '', '12345678'])
def test_signup_validates_password(api, password):
    payload = {'username': 'newcomer', 'email': 'new@test.local'}
    if password is not None:
        payload['password'] = password
    assert api.post('/api/users/', payload).status_code == 400


def test_profile_update_and_admin_user_controls(api, owner, member):
    auth(api, member)
    assert api.patch(f'/api/users/{owner.pk}/', {'first_name': 'Other'}).status_code == 404
    assert api.patch(f'/api/users/{member.pk}/', {'is_staff': True}).data['is_staff'] is False
    assert api.patch(f'/api/users/{member.pk}/', {'password': 'short'}).status_code == 400
    response = api.patch(f'/api/users/{member.pk}/', {'first_name': 'Changed', 'password': 'safer-long-password-98!'})
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.check_password('safer-long-password-98!')
    assert api.delete(f'/api/users/{member.pk}/').status_code == 403
    admin = make_user('administrator', is_staff=True)
    auth(api, admin)
    assert api.patch(f'/api/users/{member.pk}/', {'is_staff': True, 'is_active': False}).status_code == 200
    member.refresh_from_db()
    assert member.is_staff and not member.is_active
    assert api.patch(f'/api/users/{admin.pk}/', {'is_staff': False}).status_code == 400
    assert api.delete(f'/api/users/{admin.pk}/').status_code == 403
    assert api.delete(f'/api/users/{member.pk}/').status_code == 204


@pytest.mark.parametrize('days', ['bad', -1, 3651, None])
def test_invalid_invite_duration_is_validation_error(api, owner, team, days):
    auth(api, owner)
    assert api.post(f'/api/teams/{team.pk}/invite_link/', {'days': days}, format='json').status_code == 400


def test_invites_can_be_listed_revoked_and_expire(api, owner, outsider, member, team):
    auth(api, owner)
    invite = api.post(f'/api/teams/{team.pk}/invite_link/', {'days': 0}).data
    assert invite['expires_at'] is None
    assert len(api.get(f'/api/teams/{team.pk}/invite_link/').data) == 1
    assert api.delete(f"/api/teams/{team.pk}/invite_links/{invite['token']}/").status_code == 204
    auth(api, outsider)
    assert api.get(f"/api/join/{invite['token']}/preview/").status_code == 404
    assert api.post(f"/api/join/{invite['token']}/").status_code == 404
    assert api.get(f'/api/teams/{team.pk}/').status_code == 404
    auth(api, member)
    assert api.get(f'/api/teams/{team.pk}/members/').status_code == 200
    assert api.get(f'/api/teams/{team.pk}/invite_link/').status_code == 403


def test_role_assignment_gives_owner_permissions_and_protects_founder(api, owner, member, outsider, team):
    auth(api, owner)
    path = f'/api/teams/{team.pk}/members/'
    assert api.post(path, {'username': outsider.username, 'role': 'guest'}).status_code == 201
    assert api.post(path, {'username': outsider.username}).status_code == 400
    assert api.post(path, {'username': 'missing'}).status_code == 400
    assert api.patch(path, {'username': member.username, 'role': 'invalid'}).status_code == 400
    assert api.patch(path, {'username': member.username, 'role': 'owner'}).status_code == 200
    auth(api, member)
    assert api.patch(f'/api/teams/{team.pk}/', {'description': 'Delegated owner'}).status_code == 200
    assert api.post(f'/api/teams/{team.pk}/invite_link/').status_code == 201
    assert api.patch(path, {'username': owner.username, 'role': 'guest'}).status_code == 400
    assert api.delete(path).status_code == 400
    assert api.delete(path + '?username=' + outsider.username).status_code == 204
    assert not team.members.filter(pk=outsider.pk).exists()


def session_payload(team):
    now = timezone.now()
    return {'team_id': team.pk, 'title': 'Scheduled lunch', 'start_time': now.isoformat(),
            'end_time': (now + timezone.timedelta(hours=1)).isoformat()}


def test_session_creation_uses_system_defaults_and_validates_schedule(api, owner, member, team):
    SystemSettings.objects.create(default_selection_algorithm='random', default_voting_mode='single')
    payload = session_payload(team)
    auth(api, member)
    assert api.post('/api/sessions/', payload).status_code == 400
    auth(api, owner)
    response = api.post('/api/sessions/', payload)
    assert response.status_code == 201
    assert response.data['selection_algorithm'] == 'random'
    assert response.data['voting_mode'] == 'single'
    assert api.post('/api/sessions/', {**payload, 'end_time': payload['start_time']}).status_code == 400
    assert api.post('/api/sessions/', {**payload, 'is_recurring': True}).status_code == 400
    assert api.post('/api/sessions/', {**payload, 'is_recurring': True, 'recurrence_rule': 'daily'}).status_code == 201


def test_only_owner_can_edit_delete_clone_sessions(api, owner, member, team, session):
    auth(api, member)
    assert api.patch(f'/api/sessions/{session.pk}/', {'title': 'Hijacked'}).status_code == 403
    assert api.delete(f'/api/sessions/{session.pk}/').status_code == 403
    assert api.post(f'/api/sessions/{session.pk}/clone/').status_code == 403
    auth(api, owner)
    assert api.patch(f'/api/sessions/{session.pk}/', {'title': 'Updated'}).status_code == 200
    clone = api.post(f'/api/sessions/{session.pk}/clone/').data
    assert clone['team']['id'] == team.pk and clone['id'] != session.pk
    assert api.delete(f"/api/sessions/{clone['id']}/").status_code == 204
    other = make_team(owner, 'Second team')
    assert api.patch(f'/api/sessions/{session.pk}/', {'team_id': other.pk}).status_code == 400


def test_anonymous_votes_remain_private_even_to_owner(api, owner, member, team, session, restaurant):
    session.is_anonymous = True
    session.save()
    proposal = make_session_proposal(session, restaurant, owner)
    Vote.objects.create(session=session, voter=member, proposal=proposal, choice=4)
    auth(api, owner)
    assert api.get(f'/api/sessions/{session.pk}/votes/').data == []
    assert api.get(f'/api/analytics/team/{team.pk}/').data['participation'] == []
    auth(api, member)
    assert api.get(f'/api/sessions/{session.pk}/votes/').data[0]['voter'] == member.pk


@pytest.mark.parametrize('mode, count', [('single', 1), ('multiple', 2), ('rating', 2)])
def test_voting_modes_and_switching(api, member, owner, session, restaurant, mode, count):
    session.voting_mode = mode
    session.save()
    first = make_session_proposal(session, restaurant, owner)
    second = make_session_proposal(session, make_restaurant('Other place'), owner)
    auth(api, member)
    path = f'/api/sessions/{session.pk}/votes/'
    assert api.post(path, {'proposal': first.pk, 'choice': 4}).status_code == 201
    assert api.post(path, {'proposal': second.pk, 'choice': 5}).status_code == 201
    votes = Vote.objects.filter(session=session, voter=member)
    assert votes.count() == count
    assert votes.get(proposal=second).choice == (5 if mode == 'rating' else 1)
    assert api.put(path, {'proposal': second.pk, 'choice': 2}).status_code == 200
    assert api.delete(path, {'proposal': second.pk}).status_code == 204


def test_rate_limit_counts_updates_and_deletes(api, owner, session, restaurant):
    proposal = make_session_proposal(session, restaurant, owner)
    auth(api, owner)
    path = f'/api/sessions/{session.pk}/votes/'
    for value in [1, 2, 3, 4, 5]:
        assert api.post(path, {'proposal': proposal.pk, 'choice': value}).status_code in [200, 201]
    assert api.delete(path, {'proposal': proposal.pk}).status_code == 429


@pytest.mark.parametrize('bad_id', ['abc', -1, None, [1]])
def test_invalid_vote_ids_do_not_crash(api, owner, session, bad_id):
    auth(api, owner)
    assert api.post(f'/api/sessions/{session.pk}/votes/', {'proposal': bad_id}, format='json').status_code == 400


def test_votes_cannot_target_other_sessions_or_change_after_close(api, owner, team, session, restaurant):
    other = make_session(team, owner)
    proposal = make_session_proposal(other, restaurant, owner)
    auth(api, owner)
    path = f'/api/sessions/{session.pk}/votes/'
    assert api.post(path, {'proposal': proposal.pk}).status_code == 400
    own = make_session_proposal(session, restaurant, owner)
    Vote.objects.create(session=session, voter=owner, proposal=own)
    session.end_time = timezone.now() - timezone.timedelta(seconds=1)
    session.save()
    assert api.delete(path, {'proposal': own.pk}).status_code == 400
    assert Vote.objects.filter(session=session).exists()


def test_proposals_reject_menu_items_from_another_restaurant(api, owner, session, restaurant):
    wrong = make_menu_item(make_restaurant('Wrong restaurant'))
    auth(api, owner)
    response = api.post(f'/api/sessions/{session.pk}/proposals/', {'restaurant': restaurant.pk, 'menu_items': [wrong.pk]}, format='json')
    assert response.status_code == 400


def test_rules_cannot_change_after_votes(api, owner, session, restaurant):
    proposal = make_session_proposal(session, restaurant, owner)
    Vote.objects.create(session=session, voter=owner, proposal=proposal)
    auth(api, owner)
    assert api.patch(f'/api/sessions/{session.pk}/', {'is_anonymous': True}).status_code == 400
    assert api.patch(f'/api/sessions/{session.pk}/', {'voting_mode': 'single'}).status_code == 400


def test_rating_result_uses_score_and_finalization_is_idempotent(owner, member, team, session, restaurant):
    first = make_session_proposal(session, restaurant, owner)
    second = make_session_proposal(session, make_restaurant('Higher score'), owner)
    Vote.objects.create(session=session, proposal=first, voter=owner, choice=1)
    Vote.objects.create(session=session, proposal=first, voter=member, choice=1)
    Vote.objects.create(session=session, proposal=second, voter=member, choice=5)
    session.end_time = timezone.now() - timezone.timedelta(seconds=1)
    session.save()
    result, created = finalize_session(session.pk)
    assert created and result.selected_proposal == second
    again, created = finalize_session(session.pk)
    assert not created and again == result
    assert Notification.objects.filter(session=session).count() == team.members.count()


def test_random_and_weighted_algorithms_use_configured_weights(owner, session, restaurant):
    first = make_session_proposal(session, restaurant, owner)
    second = make_session_proposal(session, make_restaurant('Second'), owner)
    Vote.objects.create(session=session, voter=owner, proposal=first, choice=4)
    session.selection_algorithm = 'random'
    with patch('core.utils.random.choice', return_value=second) as choose:
        assert select_winning_proposal(session)[0] == second
        assert len(choose.call_args.args[0]) == 2
    session.selection_algorithm = 'weighted'
    SystemSettings.objects.create(weighted_base_weight=3)
    with patch('core.utils.random.choices', return_value=[first]) as choose:
        assert select_winning_proposal(session)[0] == first
        assert choose.call_args.kwargs['weights'] == [7, 3]


def test_scheduled_worker_selects_and_notifies_and_advances(owner, team, restaurant):
    ended = make_session(team, owner, active=False, recurring=True, rule='daily')
    make_session_proposal(ended, restaurant, owner)
    call_command('process_sessions')
    call_command('process_sessions')
    assert SelectionResult.objects.filter(session=ended).count() == 1
    assert ended.next_occurrences.count() == 1
    assert ended.next_occurrences.get().end_time > timezone.now()
    empty = make_session(team, owner, active=False, recurring=True, rule='weekly')
    call_command('process_sessions')
    assert empty.next_occurrences.count() == 1
    assert not SelectionResult.objects.filter(session=empty).exists()


def test_results_require_close_and_owner_and_become_read_only(api, owner, member, session, restaurant):
    make_session_proposal(session, restaurant, owner)
    auth(api, member)
    assert api.post(f'/api/sessions/{session.pk}/result/').status_code == 403
    auth(api, owner)
    assert api.post(f'/api/sessions/{session.pk}/result/').status_code == 400
    session.end_time = timezone.now() - timezone.timedelta(seconds=1)
    session.save()
    assert api.post(f'/api/sessions/{session.pk}/result/').status_code == 201
    assert api.post(f'/api/sessions/{session.pk}/result/').status_code == 200
    assert api.get(f'/api/sessions/{session.pk}/result/').status_code == 200
    assert api.patch(f'/api/sessions/{session.pk}/', {'title': 'After result'}).status_code == 400


def test_moderation_cannot_add_proposals_after_deadline(api, owner, member, session, restaurant):
    auth(api, member)
    ticket = api.post(f'/api/sessions/{session.pk}/suggestions/', {'restaurant': restaurant.pk}).data
    session.end_time = timezone.now() - timezone.timedelta(seconds=1)
    session.save()
    auth(api, owner)
    assert api.post(f"/api/suggestions/{ticket['id']}/approve/").status_code == 400
    assert not session.proposals.exists()


@pytest.mark.parametrize('suffix', ['team', 'history/team'])
def test_analytics_rejects_outsiders(api, outsider, team, suffix):
    auth(api, outsider)
    assert api.get(f'/api/analytics/{suffix}/{team.pk}/').status_code == 403


@pytest.mark.parametrize('query', ['start=bad', 'end=bad', 'start=2026-10-10&end=2026-10-01'])
def test_analytics_validates_date_ranges(api, owner, team, query):
    auth(api, owner)
    assert api.get(f'/api/analytics/team/{team.pk}/?{query}').status_code == 400
    assert api.get(f'/api/analytics/history/team/{team.pk}/?{query}').status_code == 400


def test_analytics_date_end_includes_entire_day(api, owner, session, restaurant):
    proposal = make_session_proposal(session, restaurant, owner)
    SelectionResult.objects.create(session=session, selected_proposal=proposal, method_used='majority')
    auth(api, owner)
    date = session.end_time.date().isoformat()
    assert len(api.get(f'/api/analytics/history/me/?end={date}&restaurant={restaurant.pk}').data) == 1
    assert api.get(f'/api/analytics/team/{session.team_id}/?end={date}').data['total_sessions'] == 1


def test_settings_and_system_metrics_are_admin_only_for_changes(api, owner, team):
    auth(api, owner)
    assert api.get('/api/settings/').status_code == 200
    assert api.patch('/api/settings/', {'weighted_base_weight': 2}).status_code == 403
    assert api.get('/api/analytics/system/').status_code == 403
    admin = make_user('siteadmin', is_staff=True)
    auth(api, admin)
    assert api.patch('/api/settings/', {'weighted_base_weight': 0}).status_code == 400
    assert api.patch('/api/settings/', {'default_voting_mode': 'invalid'}).status_code == 400
    assert api.patch('/api/settings/', {'allow_anonymous_voting': False}).status_code == 200
    response = api.post('/api/sessions/', {**session_payload(team), 'is_anonymous': True})
    assert response.status_code == 400
    assert api.get('/api/analytics/system/').data['teams'] == 1


@pytest.mark.parametrize('field,value', [('average_price', -1), ('rating', 6), ('rating', -1)])
def test_restaurant_range_validation(api, field, value):
    auth(api, make_user('catalogadmin', is_staff=True))
    assert api.post('/api/restaurants/', {'name': 'Place', 'cuisine_type': 'asian', field: value}).status_code == 400


def test_catalog_edit_and_nested_menu_integrity(api, restaurant):
    auth(api, make_user('catalogadmin', is_staff=True))
    assert api.patch(f'/api/restaurants/{restaurant.pk}/', {'website_url': 'https://example.org', 'rating': 4.5}).status_code == 200
    assert api.post('/api/restaurants/', {'name': restaurant.name.lower(), 'address': restaurant.address.lower(), 'cuisine_type': 'asian'}).status_code == 400
    path = f'/api/restaurants/{restaurant.pk}/menu-items/'
    assert api.post(path, {'name': 'Dish', 'price': -1}).status_code == 400
    response = api.post(path, {'name': 'Dish', 'price': 2, 'is_vegan': True, 'is_gluten_free': True})
    assert response.status_code == 201, response.data
    item = response.data
    assert api.patch(f"{path}{item['id']}/", {'price': 3}).status_code == 200
    assert api.post('/api/restaurants/999999/menu-items/', {'name': 'Dish', 'price': 1}).status_code == 404


def test_demo_seed_preserves_owner_role():
    call_command('seed_demo')
    call_command('seed_demo')
    assert get_user_model().objects.count() == 4
    assert Team.objects.get(name='Office Squad').memberships.get(user__username='sabina').role == 'owner'
    assert LunchSession.objects.count() == 1
