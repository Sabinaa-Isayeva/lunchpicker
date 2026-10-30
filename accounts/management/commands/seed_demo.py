"""Seed demo data matching the frontend mock."""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from restaurants.models import MenuItem, Restaurant
from sessions.models import LunchSession, SessionProposal, Vote
from teams.models import Membership, Team

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo users, team, restaurants, menu items and an active lunch session."

    def handle(self, *args, **options):
        users_data = [
            ("sabina", "Sabina", "Isayeva", "Team Lead"),
            ("ali", "Ali", "Mammadov", "DevOps Engineer"),
            ("leyla", "Leyla", "Aliyeva", "UI/UX Designer"),
            ("reshad", "Reshad", "Gasimov", "Backend Developer"),
        ]
        users = {}
        for username, first, last, _role in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@lunchpicker.local",
                    "first_name": first,
                    "last_name": last,
                },
            )
            if created:
                user.set_password("lunch1234")
                user.save()
            users[username] = user

        team, _ = Team.objects.get_or_create(
            name="Office Squad",
            defaults={"description": "Daily office lunch crew", "created_by": users["sabina"]},
        )
        Membership.objects.update_or_create(team=team, user=users["sabina"], defaults={"role": Membership.Role.OWNER})
        for username in ("ali", "leyla", "reshad"):
            Membership.objects.get_or_create(team=team, user=users[username], defaults={"role": Membership.Role.MEMBER})

        restaurants_data = [
            {
                "name": "Baku Pizza House",
                "address": "Nizami kuc. 14",
                "cuisine_type": Restaurant.CuisineType.EUROPEAN,
                "average_price": 15.00,
                "rating": 4.5,
                "menu": [("Margarita Pizza", True), ("Pepperoni Special", False)],
            },
            {
                "name": "Anadolu Kebap",
                "address": "Fuzuli kuc. 88",
                "cuisine_type": Restaurant.CuisineType.TURKISH,
                "average_price": 12.00,
                "rating": 4.3,
                "menu": [("Tavuk Sis Menu", False)],
            },
            {
                "name": "Dolma House",
                "address": "Tabriz kuc. 12",
                "cuisine_type": Restaurant.CuisineType.NATIONAL,
                "average_price": 14.00,
                "rating": 4.7,
                "menu": [("Yarpaq Dolmasi", False), ("Seki Piti", False)],
            },
            {
                "name": "Wok Express",
                "address": "Neftcililer pr. 21",
                "cuisine_type": Restaurant.CuisineType.ASIAN,
                "average_price": 11.50,
                "rating": 4.1,
                "menu": [("Chicken Noodles", False), ("Veggie Spring Rolls", True)],
            },
        ]

        restaurants = {}
        for r in restaurants_data:
            restaurant, _ = Restaurant.objects.get_or_create(
                name=r["name"],
                address=r["address"],
                defaults={
                    "cuisine_type": r["cuisine_type"],
                    "average_price": r["average_price"],
                    "rating": r["rating"],
                    "created_by": users["sabina"],
                },
            )
            for item_name, veg in r["menu"]:
                MenuItem.objects.get_or_create(
                    restaurant=restaurant,
                    name=item_name,
                    defaults={"price": r["average_price"], "is_vegetarian": veg},
                )
            restaurants[r["name"]] = restaurant

        now = timezone.now()
        session = LunchSession.objects.filter(title="Cume Nahari Secimi").first()
        if not session:
            session = LunchSession.objects.create(
                team=team,
                title="Cume Nahari Secimi",
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(hours=1),
                selection_algorithm=LunchSession.SelectionAlgorithm.MAJORITY,
                created_by=users["sabina"],
            )

        proposals_map = [
            ("Baku Pizza House", "ali", 4),
            ("Anadolu Kebap", "leyla", 2),
            ("Dolma House", "reshad", 3),
        ]
        for rname, proposer, votes_n in proposals_map:
            proposal, _ = SessionProposal.objects.get_or_create(
                session=session,
                restaurant=restaurants[rname],
                defaults={"proposer": users[proposer]},
            )
            voters = [u for u in users.values() if random.random() < votes_n / 4 or u.username == proposer]
            for voter in voters[:votes_n]:
                Vote.objects.get_or_create(
                    session=session, voter=voter, proposal=proposal,
                    defaults={"choice": 1},
                )

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Logins: {', '.join(users)} (password: lunch1234)"
        ))
