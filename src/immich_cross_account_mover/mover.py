import logging

from .immich_client import sha1_base64

log = logging.getLogger(__name__)


class AssetMover:
    def __init__(self, source, dest, *, dry_run: bool = False):
        self.source = source
        self.dest = dest
        self.dry_run = dry_run

    def process_asset(self, asset: dict, dest_album_id: str) -> bool:
        asset_id = asset["id"]
        checksum = asset["checksum"]

        # Step 0: dedupe pre-check on destination (checksum only, no bytes).
        check = self.dest.bulk_upload_check(checksum)
        dest_asset_id = None
        if check.get("action") == "reject" and check.get("reason") == "duplicate":
            dest_asset_id = check.get("assetId")
            if dest_asset_id:
                log.info("asset %s already present on dest as %s", asset_id, dest_asset_id)
            else:
                log.warning(
                    "dedupe reported duplicate but no assetId for %s; re-uploading",
                    asset_id,
                )

        if dest_asset_id is None:
            # Step 1: transfer the original bytes.
            data = self.source.download_original(asset_id)
            actual = sha1_base64(data)
            if actual != checksum:
                log.error(
                    "integrity check failed for %s (%s != %s); leaving on source",
                    asset_id, actual, checksum,
                )
                return False
            result = self.dest.upload_asset(
                data,
                filename=asset["originalFileName"],
                device_asset_id=f"album-mover-{asset_id}",
                file_created_at=asset["fileCreatedAt"],
                file_modified_at=asset["fileModifiedAt"],
            )
            dest_asset_id = result["id"]
            log.info("uploaded %s to dest as %s (%s)", asset_id, dest_asset_id, result.get("status"))

        # Step 2: ensure album membership.
        add = self.dest.add_to_album(dest_album_id, dest_asset_id)
        if not add.get("success") and add.get("error") != "duplicate":
            log.error(
                "failed to add %s to album %s (%s); leaving on source",
                dest_asset_id, dest_album_id, add.get("error"),
            )
            return False

        # Step 3: verification gate.
        if not self._verify(dest_asset_id, checksum, dest_album_id):
            log.error(
                "verification failed for dest asset %s; leaving source asset %s",
                dest_asset_id, asset_id,
            )
            return False

        # Step 4: trash on source (the only mutation of account A).
        if self.dry_run:
            log.info("[dry-run] would trash source asset %s", asset_id)
            return False
        self.source.trash_assets([asset_id])
        log.info("trashed source asset %s (moved to dest %s)", asset_id, dest_asset_id)
        return True

    def _verify(self, dest_asset_id: str, checksum: str, dest_album_id: str) -> bool:
        info = self.dest.get_asset(dest_asset_id)
        if info.get("checksum") != checksum:
            return False
        if info.get("isTrashed") is not False:
            return False
        album = self.dest.get_album(dest_album_id)
        member_ids = {a["id"] for a in album.get("assets", [])}
        return dest_asset_id in member_ids
