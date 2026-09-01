import pytest

from restaurants.models import Restaurant

pytestmark = [pytest.mark.django_db]


def test_anyone_authenticated_can_read_restaurants(api, owner, restaurant):
    from tests.conftest import auth

    auth(api, owner)
    res = api.get("/api/restaurants/")
    assert res.status_code == 200


def test_only_admin_can_create_restaurant(api, member, team):
    from tests.conftest import auth, make_user

    admin = make_user("admin", is_staff=True)
    auth(api, member)
    assert api.post("/api/restaurants/", {"name": "X", "cuisine_type": "asian"}).status_code == 403
    auth(api, admin)
    res = api.post("/api/restaurants/", {"name": "Admin Place", "cuisine_type": "asian", "average_price": 9})
    assert res.status_code == 201


def test_menu_item_must_match_url_restaurant(api, owner, restaurant):
    from tests.conftest import auth, make_user, make_restaurant

    other = make_restaurant(name="Other Place")
    admin = make_user("admin2", is_staff=True)
    auth(api, admin)
    res = api.post(
        f"/api/restaurants/{other.pk}/menu-items/",
        {"name": "Wrong Item", "price": 5, "restaurant": restaurant.pk},
    )
    assert res.status_code == 400


def test_restaurant_filter_by_cuisine(api, owner):
    from tests.conftest import auth, make_restaurant

    make_restaurant(name="Euro Spot", cuisine="european")
    make_restaurant(name="Asia Spot", cuisine="asian")
    auth(api, owner)
    res = api.get("/api/restaurants/?cuisine_type=asian")
    names = [r["name"] for r in res.data["results"]]
    assert names == ["Asia Spot"]
