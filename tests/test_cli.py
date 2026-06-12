from immich_cross_account_mover.__main__ import build_parser


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.config == "/config/config.yaml"
    assert args.dry_run is False
    assert args.once is False


def test_parser_flags():
    args = build_parser().parse_args(["--config", "/c.yaml", "--dry-run", "--once"])
    assert args.config == "/c.yaml"
    assert args.dry_run is True
    assert args.once is True
