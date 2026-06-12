import os
import yaml
from pydantic import BaseModel


class Mapping(BaseModel):
    source_album: str
    dest_album: str


class Config(BaseModel):
    immich_base_url: str
    poll_interval_seconds: int = 90
    mappings: list[Mapping]
    source_api_key: str
    dest_api_key: str


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data["source_api_key"] = _require_env("IMMICH_API_KEY_SOURCE")
    data["dest_api_key"] = _require_env("IMMICH_API_KEY_DEST")
    return Config(**data)
