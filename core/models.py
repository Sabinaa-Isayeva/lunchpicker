from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class SystemSettings(models.Model):
    weighted_base_weight = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(1000)])
    default_selection_algorithm = models.CharField(
        max_length=20,
        default="majority",
        choices=[("majority", "Majority"), ("random", "Random"), ("weighted", "Weighted")],
    )
    default_voting_mode = models.CharField(max_length=20, default="rating", choices=[("single", "Single choice"), ("multiple", "Multiple choice"), ("rating", "Rating 1-5")])
    voting_deadline_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1), MaxValueValidator(10080)])
    allow_anonymous_voting = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"Settings (updated {self.updated_at:%Y-%m-%d})"

    @classmethod
    def current(cls):
        # Reading defaults should not write to the database.
        return cls.objects.order_by("pk").first() or cls()
