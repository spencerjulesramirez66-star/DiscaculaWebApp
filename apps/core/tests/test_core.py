import pytest
from django.test import override_settings
from django.urls import reverse

from apps.core.assets import ManifestNotFound, asset_url, avatar_manifest, load_manifest


@pytest.mark.django_db
def test_bare_address_goes_to_home_page(client):
    response = client.get("/")
    assert response.status_code == 302 and response.url == "/home/"
    with override_settings(SITE_NAME="Renamed App"):
        response = client.get("/home/")
    assert response.status_code == 200
    assert "Renamed App" in response.content.decode()


@pytest.mark.django_db
def test_home_sends_logged_in_users_to_their_page(teacher_client):
    assert teacher_client.get("/home/").url == reverse("accounts:after_login")


def test_fruit_blender_manifest_loads():
    manifest = load_manifest("games/fruit_blender")
    assert {f["id"] for f in manifest["fruits"]} >= {"apple", "banana"}


def test_avatar_manifest_follows_setting():
    assert avatar_manifest()["id"] == "default"


def test_missing_manifest_raises():
    with pytest.raises(ManifestNotFound):
        load_manifest("does/not/exist")


def test_asset_url():
    assert asset_url("games/fruit_blender", "sprites/fruits/apple.svg").endswith(
        "assets/games/fruit_blender/sprites/fruits/apple.svg"
    )
