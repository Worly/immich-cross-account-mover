import logging
import time

log = logging.getLogger(__name__)


class Poller:
    def __init__(self, config, source, dest, mover, *, sleep=time.sleep):
        self.config = config
        self.source = source
        self.dest = dest
        self.mover = mover
        self.sleep = sleep

    def resolve_mappings(self) -> list[tuple[str, str]]:
        resolved: list[tuple[str, str]] = []
        for mapping in self.config.mappings:
            source_id = self.source.resolve_album_id(mapping.source_album)
            if not source_id:
                log.error("source album %r not found; skipping mapping", mapping.source_album)
                continue
            dest_id = self.dest.resolve_album_id(mapping.dest_album)
            if not dest_id:
                log.error("dest album %r not found on destination; skipping mapping", mapping.dest_album)
                continue
            resolved.append((source_id, dest_id))
        return resolved

    def run_once(self) -> None:
        for source_id, dest_id in self.resolve_mappings():
            try:
                album = self.source.get_album(source_id)
                for asset in album.get("assets", []):
                    try:
                        self.mover.process_asset(asset, dest_id)
                    except Exception:
                        log.exception("error processing asset %s; leaving on source", asset.get("id"))
            except Exception:
                log.exception("error fetching album %s; skipping this cycle", source_id)

    def run_forever(self) -> None:
        while True:
            try:
                self.run_once()
            except Exception:
                log.exception("unexpected error in poll cycle; will retry")
            self.sleep(self.config.poll_interval_seconds)
