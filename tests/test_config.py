import pytest
from immich_cross_account_mover.config import load_config


def _write_yaml(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "immich_base_url: http://immich-server:2283/api\n"
        "poll_interval_seconds: 90\n"
        "mappings:\n"
        "  - source_album: Trip\n"
        "    dest_album: Shared\n"
    )
    return p


def test_load_config_reads_yaml_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("IMMICH_API_KEY_SOURCE", "keyA")
    monkeypatch.setenv("IMMICH_API_KEY_DEST", "keyB")
    cfg = load_config(str(_write_yaml(tmp_path)))
    assert cfg.immich_base_url == "http://immich-server:2283/api"
    assert cfg.poll_interval_seconds == 90
    assert cfg.source_api_key == "keyA"
    assert cfg.dest_api_key == "keyB"
    assert cfg.mappings[0].source_album == "Trip"
    assert cfg.mappings[0].dest_album == "Shared"


def test_load_config_missing_env_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("IMMICH_API_KEY_SOURCE", raising=False)
    monkeypatch.setenv("IMMICH_API_KEY_DEST", "keyB")
    with pytest.raises(ValueError, match="IMMICH_API_KEY_SOURCE"):
        load_config(str(_write_yaml(tmp_path)))
