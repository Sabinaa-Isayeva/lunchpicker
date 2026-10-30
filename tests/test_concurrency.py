from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection, connections

from sessions.models import Notification, SelectionResult
from sessions.services import finalize_session
from tests.conftest import make_session_proposal


@pytest.mark.django_db(transaction=True)
def test_concurrent_finalization_creates_one_result_and_notification_set(owner, team, session, restaurant):
    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL row-lock regression; SQLite does not provide select_for_update.')
    from django.utils import timezone
    make_session_proposal(session, restaurant, owner)
    session.end_time = timezone.now() - timezone.timedelta(seconds=1)
    session.is_recurring = True
    session.recurrence_rule = 'daily'
    session.save()

    def select(_):
        close_old_connections()
        try:
            result, created = finalize_session(session.pk)
            return result.pk, created
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(select, [1, 2]))
    assert results[0][0] == results[1][0]
    assert sum(created for _, created in results) == 1
    assert SelectionResult.objects.filter(session=session).count() == 1
    assert Notification.objects.filter(session=session).count() == team.members.count()
    assert session.next_occurrences.count() == 1
