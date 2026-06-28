import base64
import hashlib
import time
import uuid

import httpx

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class ImmichError(Exception):
    pass


def sha1_base64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha1(data).digest()).decode()


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


class ImmichClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 60.0,
        max_attempts: int = 4,
        backoff_base: float = 0.5,
        sleep=time.sleep,
    ):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"x-api-key": api_key, "Accept": "application/json"},
            timeout=timeout,
        )
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _send(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last_error = exc
            else:
                if response.status_code not in _TRANSIENT_STATUS:
                    response.raise_for_status()
                    return response
                last_error = ImmichError(f"{response.status_code} from {method} {url}")
            if attempt < self._max_attempts:
                self._sleep(self._backoff_base * (2 ** (attempt - 1)))
        raise ImmichError(
            f"{method} {url} failed after {self._max_attempts} attempts: {last_error}"
        ) from last_error

    def get_me(self) -> dict:
        return self._send("GET", "/users/me").json()

    def list_albums(self) -> list[dict]:
        return self._send("GET", "/albums").json()

    def get_album(self, album_id: str) -> dict:
        return self._send("GET", f"/albums/{album_id}").json()

    def bulk_upload_check(self, checksum: str) -> dict:
        body = {"assets": [{"id": "check", "checksum": checksum}]}
        data = self._send("POST", "/assets/bulk-upload-check", json=body).json()
        return data["results"][0]

    def download_original(self, asset_id: str) -> bytes:
        return self._send("GET", f"/assets/{asset_id}/original").content

    def upload_asset(
        self,
        data: bytes,
        *,
        filename: str,
        device_asset_id: str,
        file_created_at: str,
        file_modified_at: str,
    ) -> dict:
        files = {"assetData": (filename, data, "application/octet-stream")}
        form = {
            "deviceAssetId": device_asset_id,
            "deviceId": "album-mover",
            "fileCreatedAt": file_created_at,
            "fileModifiedAt": file_modified_at,
        }
        return self._send("POST", "/assets", data=form, files=files).json()

    def add_to_album(self, album_id: str, asset_id: str) -> dict:
        body = {"ids": [asset_id]}
        results = self._send("PUT", f"/albums/{album_id}/assets", json=body).json()
        if not results:
            raise ImmichError(
                f"add_to_album: empty result for asset {asset_id!r} in album {album_id!r}"
            )
        return results[0]

    def remove_from_album(self, album_id: str, asset_id: str) -> dict:
        """Drop an asset from an album. The album itself is never deleted, even
        when this removes its last member. An empty result (asset already absent)
        is reported as success, since the desired end state is reached either way.
        """
        body = {"ids": [asset_id]}
        results = self._send("DELETE", f"/albums/{album_id}/assets", json=body).json()
        if not results:
            return {"id": asset_id, "success": True}
        return results[0]

    def get_asset(self, asset_id: str) -> dict:
        return self._send("GET", f"/assets/{asset_id}").json()

    def trash_assets(self, asset_ids: list[str]) -> None:
        if not asset_ids:
            return
        body = {"ids": asset_ids, "force": False}
        self._send("DELETE", "/assets", json=body)

    def resolve_album_id(self, name_or_id: str) -> str | None:
        """Resolve an album name or ID to an album ID, or None if not found.

        If name_or_id is a syntactically valid UUID it is treated as an ID and
        looked up directly (a 404 yields None; transient/other errors propagate).
        Otherwise albums are scanned by name and the FIRST matching album's ID is
        returned.
        """
        if _is_uuid(name_or_id):
            try:
                self.get_album(name_or_id)
                return name_or_id
            except httpx.HTTPStatusError:
                return None
        for album in self.list_albums():
            if album.get("albumName") == name_or_id:
                return album["id"]
        return None
