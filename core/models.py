from django.db import models

class SystemSettings(models.Model):
    default_selection_algorithm = models.CharField(
        max_length=20,
        default="majority",
        choices=[("majority", "Majority"), ("random", "Random"), ("weighted", "Weighted")],
    )
    default_voting_mode = models.CharField(max_length=20, default="rating")
    voting_deadline_minutes = models.PositiveIntegerField(default=60)
    allow_anonymous_voting = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"Settings (updated {self.updated_at:%Y-%m-%d})"
