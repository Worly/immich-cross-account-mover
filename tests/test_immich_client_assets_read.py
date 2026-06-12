import httpx
import respx
from immich_cross_account_mover.immich_client import ImmichClient


def make_client():
    return ImmichClient("http://immich/api", "secret", sleep=lambda _: None)


@respx.mock
def test_bulk_upload_check_returns_first_result():
    route = respx.post("http://immich/api/assets/bulk-upload-check").mock(
        return_value=httpx.Response(200, json={"results": [
            {"id": "check", "action": "reject", "reason": "duplicate", "assetId": "b1"}
        ]})
    )
    result = make_client().bulk_upload_check("CHK")
    assert result["assetId"] == "b1"
    sent = route.calls.last.request
    assert b"CHK" in sent.content


@respx.mock
def test_download_original_returns_bytes():
    respx.get("http://immich/api/assets/a1/original").mock(
        return_value=httpx.Response(200, content=b"rawbytes")
    )
    assert make_client().download_original("a1") == b"rawbytes"
