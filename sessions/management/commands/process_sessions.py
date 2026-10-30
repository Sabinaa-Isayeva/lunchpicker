from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from sessions.models import LunchSession
from sessions.services import finalize_session


class Command(BaseCommand):
    help = "Select results, notify members, and advance ended recurring sessions. Run every minute."

    def handle(self, *args, **options):
        ids = list(LunchSession.objects.filter(end_time__lte=timezone.now(), result__isnull=True)
                   .filter(Q(proposals__isnull=False) | Q(is_recurring=True, next_occurrences__isnull=True))
                   .values_list("pk", flat=True).distinct())
        created = 0
        for session_id in ids:
            _, new = finalize_session(session_id)
            created += int(new)
        self.stdout.write(self.style.SUCCESS(f"Finalized {created} session(s)."))
