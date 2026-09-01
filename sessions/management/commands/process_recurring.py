"""Spawn next occurrences of ended recurring sessions (spec §4.2).

Run periodically, e.g. hourly via cron / Celery beat:
    python manage.py process_recurring
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from sessions.models import LunchSession


class Command(BaseCommand):
    help = "Create the next occurrence for ended recurring lunch sessions."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        ended = LunchSession.objects.filter(
            is_recurring=True,
            end_time__lt=now,
            parent_session__isnull=True,
        ) | LunchSession.objects.filter(
            is_recurring=True,
            end_time__lt=now,
        )
        created = 0
        for session in ended.distinct():
            if session.next_occurrences.exists():
                continue
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] would create next for '{session.title}' ({session.pk})")
                continue
            nxt = session.create_next_occurrence()
            if nxt:
                created += 1
                self.stdout.write(f"Created session {nxt.pk} '{nxt.title}' starting {nxt.start_time}")
        self.stdout.write(self.style.SUCCESS(f"Done. {created} session(s) created."))
