from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class LunchSession(models.Model):
    class SelectionAlgorithm(models.TextChoices):
        MAJORITY = "majority", "Majority vote"
        RANDOM = "random", "Random draw"
        WEIGHTED = "weighted", "Weighted preference"

    class RecurrenceRule(models.TextChoices):
        DAILY = "daily", "Every day"
        WEEKLY = "weekly", "Every week"

    team = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=150)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=100, blank=True)
    selection_algorithm = models.CharField(
        max_length=20,
        choices=SelectionAlgorithm.choices,
        default=SelectionAlgorithm.MAJORITY,
    )
    is_anonymous = models.BooleanField(default=False)
    voting_mode = models.CharField(
        max_length=20,
        choices=[("single", "Single choice"), ("multiple", "Multiple choice"), ("rating", "Rating 1-5")],
        default="rating",
    )
    is_announcement = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions_created")
    parent_session = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="next_occurrences"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_time"]

    def clean(self):
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be after start_time."})
        if self.is_recurring and self.recurrence_rule not in LunchSession.RecurrenceRule.values:
            raise ValidationError({"recurrence_rule": "Recurrence rule is required for recurring sessions."})

    @property
    def is_active(self):
        from django.utils import timezone

        now = timezone.now()
        return self.start_time <= now <= self.end_time

    def create_next_occurrence(self):
        if not self.is_recurring or not self.recurrence_rule:
            return None
        if self.next_occurrences.exists():
            return None
        from django.utils import timezone as tz

        step = (tz.timedelta(days=1) if self.recurrence_rule == LunchSession.RecurrenceRule.DAILY
                else tz.timedelta(weeks=1))
        return LunchSession.objects.create(
            team=self.team,
            title=self.title,
            start_time=self.start_time + step,
            end_time=self.end_time + step,
            is_recurring=True,
            recurrence_rule=self.recurrence_rule,
            selection_algorithm=self.selection_algorithm,
            is_anonymous=self.is_anonymous,
            voting_mode=self.voting_mode,
            is_announcement=self.is_announcement,
            created_by=self.created_by,
            parent_session=self,
        )

    def __str__(self):
        return f"{self.title} ({self.team.name})"


class SessionProposal(models.Model):
    session = models.ForeignKey(LunchSession, on_delete=models.CASCADE, related_name="proposals")
    restaurant = models.ForeignKey("restaurants.Restaurant", on_delete=models.CASCADE, related_name="proposals")
    menu_items = models.ManyToManyField("restaurants.MenuItem", related_name="proposals", blank=True)
    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proposals")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["session", "restaurant"], name="uniq_restaurant_per_session"),
        ]

    def clean(self):
        if self.proposer_id and not self.session.team.members.filter(pk=self.proposer_id).exists():
            raise ValidationError({"proposer": "Proposer must be a member of the session's team."})
        for item in self.menu_items.all():
            if item.restaurant_id != self.restaurant_id:
                raise ValidationError({"menu_items": "All menu items must belong to the proposed restaurant."})

    def __str__(self):
        return f"{self.restaurant.name} @ {self.session.title}"


class Vote(models.Model):
    CHOICE_LIKE = 1
    CHOICES = [(i, str(i)) for i in range(1, 6)]

    session = models.ForeignKey(LunchSession, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="votes")
    proposal = models.ForeignKey(SessionProposal, on_delete=models.CASCADE, related_name="votes")
    choice = models.PositiveSmallIntegerField(choices=CHOICES, default=CHOICE_LIKE)
    voted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-voted_at"]
        constraints = [
            models.UniqueConstraint(fields=["session", "voter", "proposal"], name="uniq_vote_per_proposal"),
        ]

    def clean(self):
        if self.proposal_id and self.proposal.session_id != self.session_id:
            raise ValidationError({"proposal": "Vote must target a proposal within the same session."})
        if self.voter_id and not self.session.team.members.filter(pk=self.voter_id).exists():
            raise ValidationError({"voter": "Voter must be a member of the session's team."})

    def __str__(self):
        return f"{self.voter} -> {self.proposal} ({self.choice})"


class SelectionResult(models.Model):
    session = models.OneToOneField(LunchSession, on_delete=models.CASCADE, related_name="result")
    selected_proposal = models.ForeignKey(SessionProposal, on_delete=models.CASCADE, related_name="selection_results")
    method_used = models.CharField(max_length=20, choices=LunchSession.SelectionAlgorithm.choices)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]

    def __str__(self):
        return f"{self.session.title}: {self.selected_proposal.restaurant.name}"


class Suggestion(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    session = models.ForeignKey(LunchSession, on_delete=models.CASCADE, related_name="suggestions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="suggestions")
    restaurant = models.ForeignKey("restaurants.Restaurant", on_delete=models.CASCADE, related_name="suggestions")
    menu_items = models.ManyToManyField("restaurants.MenuItem", related_name="suggestions", blank=True)
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        for item in self.menu_items.all():
            if item.restaurant_id != self.restaurant_id:
                raise ValidationError({"menu_items": "All menu items must belong to the selected restaurant."})

    def __str__(self):
        return f"[{self.status}] {self.user}: {self.restaurant.name} @ {self.session.title}"


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    session = models.ForeignKey(LunchSession, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"To {self.recipient}: {self.message[:40]}"
