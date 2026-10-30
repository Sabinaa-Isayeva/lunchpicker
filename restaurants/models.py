from django.conf import settings
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from django.db import models


class Restaurant(models.Model):
    class CuisineType(models.TextChoices):
        EUROPEAN = "european", "European"
        TURKISH = "turkish", "Turkish"
        ASIAN = "asian", "Asian"
        NATIONAL = "national", "National"

    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True)
    cuisine_type = models.CharField(max_length=20, choices=CuisineType.choices)
    website_url = models.URLField(validators=[URLValidator()], blank=True)
    average_price = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="restaurants_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "address"], name="uniq_restaurant_name_address"),
        ]

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="menu_items")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["restaurant", "name"], name="uniq_menu_item_per_restaurant"),
        ]

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"
