import httpx
import pytest
import respx
from immich_cross_account_mover.immich_client import ImmichClient, ImmichError


def make_client():
    return ImmichClient("http://immich/api", "secret", sleep=lambda _: None)


@respx.mock
def test_upload_asset_posts_multipart_and_returns_dict():
    route = respx.post("http://immich/api/assets").mock(
        return_value=httpx.Response(201, json={"id": "b1", "status": "created"})
    )
    result = make_client().upload_asset(
        b"rawbytes",
        filename="IMG.jpg",
        device_asset_id="album-mover-a1",
        file_created_at="2024-01-01T00:00:00Z",
        file_modified_at="2024-01-01T00:00:00Z",
    )
    assert result == {"id": "b1", "status": "created"}
    body = route.calls.last.request.content
    assert b"album-mover-a1" in body
    assert b"rawbytes" in body
    assert b"assetData" in body


@respx.mock
def test_add_to_album_returns_first_result():
    respx.put("http://immich/api/albums/D1/assets").mock(
        return_value=httpx.Response(200, json=[{"id": "b1", "success": True}])
    )
    assert make_client().add_to_album("D1", "b1") == {"id": "b1", "success": True}


@respx.mock
def test_remove_from_album_sends_delete_with_ids():
    route = respx.delete("http://immich/api/albums/D1/assets").mock(
        return_value=httpx.Response(200, json=[{"id": "b1", "success": True}])
    )
    assert make_client().remove_from_album("D1", "b1") == {"id": "b1", "success": True}
    body = route.calls.last.request.content
    assert b"b1" in body


@respx.mock
def test_remove_from_album_empty_result_reports_success():
    respx.delete("http://immich/api/albums/D1/assets").mock(
        return_value=httpx.Response(200, json=[])
    )
    assert make_client().remove_from_album("D1", "b1")["success"] is True


@respx.mock
def test_get_asset_returns_dict():
    respx.get("http://immich/api/assets/b1").mock(
        return_value=httpx.Response(200, json={"id": "b1", "checksum": "CHK", "isTrashed": False})
    )
    assert make_client().get_asset("b1")["checksum"] == "CHK"


@respx.mock
def test_trash_assets_sends_force_false():
    route = respx.delete("http://immich/api/assets").mock(return_value=httpx.Response(204))
    make_client().trash_assets(["a1"])
    body = route.calls.last.request.content
    assert b'"force": false' in body or b'"force":false' in body
    assert b"a1" in body


@respx.mock
def test_add_to_album_raises_on_empty_result():
    respx.put("http://immich/api/albums/D1/assets").mock(
        return_value=httpx.Response(200, json=[])
    )
    with pytest.raises(ImmichError):
        make_client().add_to_album("D1", "b1")


@respx.mock
def test_trash_assets_empty_list_makes_no_request():
    route = respx.delete("http://immich/api/assets").mock(return_value=httpx.Response(204))
    make_client().trash_assets([])
    assert route.call_count == 0
