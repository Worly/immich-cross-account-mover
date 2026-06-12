import argparse
import logging
import sys

from .config import load_config
from .immich_client import ImmichClient
from .mover import AssetMover
from .poller import Poller


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="immich-cross-account-mover")
    parser.add_argument("--config", default="/config/config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    config = load_config(args.config)
    source = ImmichClient(config.immich_base_url, config.source_api_key)
    dest = ImmichClient(config.immich_base_url, config.dest_api_key)

    # Fail loud if either key is missing or lacks album access. We validate via
    # list_albums (needs album.read, which the mover requires anyway) instead of
    # /users/me, so the keys don't need the user.read permission.
    source.list_albums()
    dest.list_albums()

    mover = AssetMover(source, dest, dry_run=args.dry_run)
    poller = Poller(config, source, dest, mover)

    if args.dry_run:
        logging.getLogger(__name__).warning("DRY RUN: no assets will be trashed on source")
    if args.once:
        poller.run_once()
    else:
        poller.run_forever()


if __name__ == "__main__":
    main()
