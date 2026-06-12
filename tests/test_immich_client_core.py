import base64
import hashlib
import httpx
import pytest
import respx
from immich_cross_account_mover.immich_client import ImmichClient, ImmichError, sha1_base64


def make_client():
    return ImmichClient("http://immich/api", "secret", max_attempts=3, sleep=lambda _: None)


def test_sha1_base64_matches_known_value():
    data = b"hello"
    expected = base64.b64encode(hashlib.sha1(data).digest()).decode()
    assert sha1_base64(data) == expected


@respx.mock
def test_get_me_sends_api_key_header():
    route = respx.get("http://immich/api/users/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "email": "a@b.c"})
    )
    client = make_client()
    assert client.get_me()["id"] == "u1"
    assert route.calls.last.request.headers["x-api-key"] == "secret"


@respx.mock
def test_send_retries_on_503_then_succeeds():
    respx.get("http://immich/api/users/me").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"id": "u1"})]
    )
    client = make_client()
    assert client.get_me()["id"] == "u1"


@respx.mock
def test_send_raises_after_exhausting_retries():
    respx.get("http://immich/api/users/me").mock(return_value=httpx.Response(503))
    client = make_client()
    with pytest.raises(ImmichError):
        client.get_me()


@respx.mock
def test_send_raises_on_4xx_without_retry():
    route = respx.get("http://immich/api/users/me").mock(return_value=httpx.Response(401))
    client = make_client()
    with pytest.raises(httpx.HTTPStatusError):
        client.get_me()
    assert route.call_count == 1


@respx.mock
def test_send_retries_on_transport_error_then_succeeds():
    respx.get("http://immich/api/users/me").mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"id": "u1"})]
    )
    client = make_client()
    assert client.get_me()["id"] == "u1"
