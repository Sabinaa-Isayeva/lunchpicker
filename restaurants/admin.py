from django.contrib import admin

from restaurants.models import MenuItem, Restaurant


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ["name", "cuisine_type", "average_price", "rating", "created_by"]
    list_filter = ["cuisine_type"]
    search_fields = ["name", "address"]
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["name", "restaurant", "price", "is_vegetarian", "is_vegan", "is_gluten_free"]
    list_filter = ["restaurant__cuisine_type", "is_vegetarian", "is_vegan", "is_gluten_free"]
    search_fields = ["name"]
