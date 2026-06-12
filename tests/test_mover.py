from unittest.mock import MagicMock

from immich_cross_account_mover.immich_client import sha1_base64
from immich_cross_account_mover.mover import AssetMover

DATA = b"rawbytes"
GOOD_CHECKSUM = sha1_base64(DATA)


def make_asset(asset_id="a1", checksum=GOOD_CHECKSUM, name="IMG.jpg"):
    return {
        "id": asset_id,
        "checksum": checksum,
        "originalFileName": name,
        "fileCreatedAt": "2024-01-01T00:00:00Z",
        "fileModifiedAt": "2024-01-01T00:00:00Z",
    }


def make_clients(dest_asset_id="b1", dup=False, trashed=False, verify_checksum=GOOD_CHECKSUM, in_album=True):
    source = MagicMock()
    dest = MagicMock()
    if dup:
        dest.bulk_upload_check.return_value = {"action": "reject", "reason": "duplicate", "assetId": dest_asset_id}
    else:
        dest.bulk_upload_check.return_value = {"action": "accept"}
        dest.upload_asset.return_value = {"id": dest_asset_id, "status": "created"}
    source.download_original.return_value = DATA
    dest.add_to_album.return_value = {"id": dest_asset_id, "success": True}
    dest.get_asset.return_value = {"id": dest_asset_id, "checksum": verify_checksum, "isTrashed": trashed}
    dest.get_album.return_value = {"id": "D", "assets": [{"id": dest_asset_id}] if in_album else []}
    return source, dest


def test_new_asset_uploads_then_trashes():
    source, dest = make_clients()
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is True
    dest.upload_asset.assert_called_once()
    source.trash_assets.assert_called_once_with(["a1"])


def test_already_in_dest_skips_upload_then_trashes():
    source, dest = make_clients(dup=True)
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is True
    source.download_original.assert_not_called()
    dest.upload_asset.assert_not_called()
    source.trash_assets.assert_called_once_with(["a1"])


def test_integrity_mismatch_aborts_without_upload_or_trash():
    source, dest = make_clients()
    mover = AssetMover(source, dest)
    asset = make_asset(checksum="WRONGCHECKSUM")
    assert mover.process_asset(asset, "D") is False
    dest.upload_asset.assert_not_called()
    source.trash_assets.assert_not_called()


def test_verify_checksum_mismatch_does_not_trash():
    source, dest = make_clients(verify_checksum="DIFFERENT")
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is False
    source.trash_assets.assert_not_called()


def test_verify_trashed_dest_does_not_trash():
    source, dest = make_clients(trashed=True)
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is False
    source.trash_assets.assert_not_called()


def test_verify_not_in_album_does_not_trash():
    source, dest = make_clients(in_album=False)
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is False
    source.trash_assets.assert_not_called()


def test_add_to_album_duplicate_is_treated_as_success():
    source, dest = make_clients()
    dest.add_to_album.return_value = {"id": "b1", "success": False, "error": "duplicate"}
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is True
    source.trash_assets.assert_called_once_with(["a1"])


def test_add_to_album_real_failure_does_not_trash():
    source, dest = make_clients()
    dest.add_to_album.return_value = {"id": "b1", "success": False, "error": "no_permission"}
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is False
    source.trash_assets.assert_not_called()


def test_dry_run_never_trashes():
    source, dest = make_clients()
    mover = AssetMover(source, dest, dry_run=True)
    assert mover.process_asset(make_asset(), "D") is False
    source.trash_assets.assert_not_called()


def test_idempotent_second_run_does_not_reupload():
    source, dest = make_clients()
    dest.bulk_upload_check.side_effect = [
        {"action": "accept"},
        {"action": "reject", "reason": "duplicate", "assetId": "b1"},
    ]
    mover = AssetMover(source, dest)
    mover.process_asset(make_asset(), "D")
    mover.process_asset(make_asset(), "D")
    assert dest.upload_asset.call_count == 1
    assert source.trash_assets.call_count == 2


def test_dedupe_duplicate_without_assetid_falls_through_to_upload():
    source, dest = make_clients()
    dest.bulk_upload_check.return_value = {"action": "reject", "reason": "duplicate"}
    mover = AssetMover(source, dest)
    assert mover.process_asset(make_asset(), "D") is True
    source.download_original.assert_called_once()
    dest.upload_asset.assert_called_once()
    source.trash_assets.assert_called_once_with(["a1"])
