import httpx
import respx
from immich_cross_account_mover.immich_client import ImmichClient


def make_client():
    return ImmichClient("http://immich/api", "secret", sleep=lambda _: None)


@respx.mock
def test_get_album_returns_assets():
    respx.get("http://immich/api/albums/A1").mock(
        return_value=httpx.Response(200, json={"id": "A1", "assets": [{"id": "x"}]})
    )
    assert make_client().get_album("A1")["assets"][0]["id"] == "x"


@respx.mock
def test_resolve_album_id_by_name():
    respx.get("http://immich/api/albums").mock(
        return_value=httpx.Response(200, json=[
            {"id": "A1", "albumName": "Trip"},
            {"id": "A2", "albumName": "Shared"},
        ])
    )
    assert make_client().resolve_album_id("Shared") == "A2"


@respx.mock
def test_resolve_album_id_name_not_found_returns_none():
    respx.get("http://immich/api/albums").mock(return_value=httpx.Response(200, json=[]))
    assert make_client().resolve_album_id("Missing") is None


@respx.mock
def test_resolve_album_id_accepts_uuid_when_present():
    uid = "11111111-1111-1111-1111-111111111111"
    respx.get(f"http://immich/api/albums/{uid}").mock(
        return_value=httpx.Response(200, json={"id": uid})
    )
    assert make_client().resolve_album_id(uid) == uid


@respx.mock
def test_resolve_album_id_uuid_absent_returns_none():
    uid = "11111111-1111-1111-1111-111111111111"
    respx.get(f"http://immich/api/albums/{uid}").mock(return_value=httpx.Response(404))
    assert make_client().resolve_album_id(uid) is None
