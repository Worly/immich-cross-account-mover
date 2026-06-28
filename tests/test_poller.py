from unittest.mock import MagicMock

import pytest

from immich_cross_account_mover.config import Config, Mapping
from immich_cross_account_mover.poller import Poller


def make_config():
    return Config(
        immich_base_url="http://immich/api",
        poll_interval_seconds=5,
        mappings=[Mapping(source_album="Trip", dest_album="Shared")],
        source_api_key="a",
        dest_api_key="b",
    )


def test_resolve_mappings_returns_resolved_pairs():
    source = MagicMock(); dest = MagicMock()
    source.resolve_album_id.return_value = "S1"
    dest.resolve_album_id.return_value = "D1"
    poller = Poller(make_config(), source, dest, MagicMock(), sleep=lambda _: None)
    assert poller.resolve_mappings() == [("S1", "D1")]


def test_resolve_mappings_skips_missing_source():
    source = MagicMock(); dest = MagicMock()
    source.resolve_album_id.return_value = None
    dest.resolve_album_id.return_value = "D1"
    poller = Poller(make_config(), source, dest, MagicMock(), sleep=lambda _: None)
    assert poller.resolve_mappings() == []


def test_resolve_mappings_skips_missing_dest():
    source = MagicMock(); dest = MagicMock()
    source.resolve_album_id.return_value = "S1"
    dest.resolve_album_id.return_value = None
    poller = Poller(make_config(), source, dest, MagicMock(), sleep=lambda _: None)
    assert poller.resolve_mappings() == []


def test_run_once_processes_each_asset():
    source = MagicMock(); dest = MagicMock(); mover = MagicMock()
    source.resolve_album_id.return_value = "S1"
    dest.resolve_album_id.return_value = "D1"
    source.get_album.return_value = {"id": "S1", "assets": [{"id": "a1"}, {"id": "a2"}]}
    poller = Poller(make_config(), source, dest, mover, sleep=lambda _: None)
    poller.run_once()
    assert mover.process_asset.call_count == 2
    mover.process_asset.assert_any_call({"id": "a1"}, "D1", "S1")


def test_run_once_isolates_per_asset_errors():
    source = MagicMock(); dest = MagicMock(); mover = MagicMock()
    source.resolve_album_id.return_value = "S1"
    dest.resolve_album_id.return_value = "D1"
    source.get_album.return_value = {"id": "S1", "assets": [{"id": "a1"}, {"id": "a2"}]}
    mover.process_asset.side_effect = [RuntimeError("boom"), True]
    poller = Poller(make_config(), source, dest, mover, sleep=lambda _: None)
    poller.run_once()  # must not raise
    assert mover.process_asset.call_count == 2


def test_run_forever_loops_until_interrupted():
    source = MagicMock(); dest = MagicMock(); mover = MagicMock()

    def stop(_):
        raise KeyboardInterrupt

    poller = Poller(make_config(), source, dest, mover, sleep=stop)
    poller.run_once = MagicMock()
    with pytest.raises(KeyboardInterrupt):
        poller.run_forever()
    poller.run_once.assert_called_once()


def test_run_once_isolates_per_album_errors():
    source = MagicMock(); dest = MagicMock(); mover = MagicMock()
    config = Config(
        immich_base_url="http://immich/api",
        poll_interval_seconds=5,
        mappings=[
            Mapping(source_album="A", dest_album="DA"),
            Mapping(source_album="B", dest_album="DB"),
        ],
        source_api_key="a",
        dest_api_key="b",
    )
    source.resolve_album_id.side_effect = ["S1", "S2"]
    dest.resolve_album_id.side_effect = ["D1", "D2"]
    source.get_album.side_effect = [RuntimeError("boom"), {"id": "S2", "assets": [{"id": "a1"}]}]
    poller = Poller(config, source, dest, mover, sleep=lambda _: None)
    poller.run_once()  # must not raise
    mover.process_asset.assert_called_once_with({"id": "a1"}, "D2", "S2")


def test_run_forever_survives_run_once_error():
    source = MagicMock(); dest = MagicMock(); mover = MagicMock()
    poller = Poller(
        make_config(), source, dest, mover,
        sleep=MagicMock(side_effect=[None, KeyboardInterrupt]),
    )
    poller.run_once = MagicMock(side_effect=[RuntimeError("boom"), None])
    with pytest.raises(KeyboardInterrupt):
        poller.run_forever()
    assert poller.run_once.call_count == 2
