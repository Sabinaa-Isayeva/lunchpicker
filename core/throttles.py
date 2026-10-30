from django.conf import settings
from django_ratelimit.core import get_usage
from rest_framework.throttling import BaseThrottle


class VoteThrottle(BaseThrottle):
    """Count all mutations atomically in the shared cache, including updates."""

    def allow_request(self, request, view):
        usage = get_usage(request, group="session-votes", key=lambda group, req: str(req.user.pk),
                          rate=f"{settings.RATELIMIT_VOTES_PER_MINUTE}/m",
                          method=get_usage.ALL, increment=True)
        self.time_left = max(usage["time_left"], 1) if usage else 0
        return usage is None or not usage["should_limit"]

    def wait(self):
        return self.time_left
