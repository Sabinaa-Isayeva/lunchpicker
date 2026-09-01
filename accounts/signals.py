from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

DEFAULT_TEAM_NAME = "Office Squad"


@receiver(post_save, dispatch_uid="accounts_add_user_to_default_team")
def add_user_to_default_team(sender, instance, created, **kwargs):
    if not created:
        return
    if sender._meta.label != settings.AUTH_USER_MODEL:
        return

    from teams.models import Membership, Team

    team = Team.objects.filter(name=DEFAULT_TEAM_NAME).first()
    if not team:
        return
    if team.members.filter(pk=instance.pk).exists():
        return
    team.members.add(instance)
    Membership.objects.get_or_create(
        team=team,
        user=instance,
        defaults={"role": Membership.Role.MEMBER},
    )
