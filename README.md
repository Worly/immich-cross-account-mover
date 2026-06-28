# immich-cross-account-mover

Safely move photos from one [Immich](https://immich.app) account to another. When a photo
appears in a watched album on a **source** account, this service copies it into a mapped album
on a **destination** account, verifies a byte-for-byte identical copy landed, and only then
moves the original to the source account's trash and clears it from the source album. The
source album is left empty but intact, ready to reuse.

Built for the case where two accounts live on the **same Immich server** (for example, moving
photos from a personal account into a shared/family account) and you want the move to be safe
enough to trust with irreplaceable photos.

> **Prime directive: never lose a photo.** The original is only trashed after a
> checksum-identical copy is confirmed present *and* a member of the destination album. The
> worst case is a photo that lingers un-moved — never one that's lost.

## How it works

Every poll cycle (default 90s), for each configured album mapping, for each photo in the
source album:

1. **Dedupe check** — ask the destination (by checksum only, no file transfer) whether it
   already has this photo.
2. **Transfer** — if not, download the original from the source, verify its SHA-1 matches the
   source-reported checksum, and upload it to the destination. The original bytes are uploaded
   untouched, so embedded EXIF/GPS is preserved.
3. **Add to album** — ensure the destination asset is in the mapped album.
4. **Verify** — confirm the destination asset's checksum matches the source, it isn't trashed,
   and it is a member of the destination album.
5. **Trash on source** — only now move the original to the source account's trash
   (`force=false`, recoverable for 30 days).
6. **Empty from the source album** — remove the trashed original from the source album so the
   album is left intact but empty, ready to reuse. The album itself is never deleted. This runs
   last and is best-effort: the photo is already safe on the destination and trashed on the
   source, so a failure here only delays the album tidy-up (the 30-day trash purge clears the
   membership regardless) and never fails the move.

Any failure at step 1–5 leaves the photo on the source and retries next cycle. A photo that
keeps failing simply stays in its source album — that lingering photo *is* your alert.

## Important caveats

- **Removing the photo from your phone is a separate, mobile-app concern.** This service only
  trashes the asset on the server. For the photo to also leave the source phone, enable
  **"Sync remote deletions"** in the Immich mobile app on the source account's device; the app
  then removes the local copy on its next sync (a review screen by default on Android,
  review-only on iOS).
- **Same-server, two-account model.** Both accounts are expected to live on one Immich server.
  The service uses one base URL and two API keys.
- **API field assumption.** The service reads `checksum`, `originalFileName`, `fileCreatedAt`,
  and `fileModifiedAt` from each asset returned by `GET /albums/{id}`. These are standard
  fields, but Immich's API evolves — verify them against your server version before trusting it
  with real photos (see [Rollout](#rollout-do-this-before-trusting-real-photos)).

## Configuration

Two API keys (one per account; Immich → Account Settings → API Keys) go in a `.env` file, and
album mappings go in `config.yaml`.

`.env`:

```dotenv
IMMICH_API_KEY_SOURCE=key-for-account-A
IMMICH_API_KEY_DEST=key-for-account-B
```

`config.yaml`:

```yaml
immich_base_url: http://immich-server:2283/api
poll_interval_seconds: 90
mappings:
  - source_album: "Trip photos"    # album name (or id) on the source account
    dest_album: "Shared trips"     # must already exist on the destination account
```

Destination albums must already exist — a mapping whose destination is missing is skipped with
a logged error (the other mappings keep working).

### API key permissions

Immich API keys are scoped. Create one key while logged in as **each** account (Account
Settings → API Keys). The simplest option is to grant **all** permissions — fine for a
self-hosted server where you own both accounts, and it sidesteps a known quirk where the
`user.*` permissions aren't always selectable in the UI.

If you prefer least privilege, grant exactly what each key uses:

| Key | Account | Permissions |
| --- | --- | --- |
| `IMMICH_API_KEY_SOURCE` | source (A) | `album.read`, `albumAsset.delete`, `asset.read`, `asset.view`, `asset.download`, `asset.delete` |
| `IMMICH_API_KEY_DEST` | destination (B) | `album.read`, `asset.read`, `asset.upload`, `albumAsset.create` |

The service does **not** need the `user.read` permission. If a scoped key still returns
`403 Forbidden`, the log line names the endpoint that was rejected — grant the matching
permission (or fall back to all).

## Running with Docker

Images are published to Docker Hub on every release as
`worly/immich-cross-account-mover` (multi-arch: `linux/amd64` + `linux/arm64`, so it runs on
a Raspberry Pi too).

```bash
cp docker-compose.example.yml docker-compose.yml
cp config.example.yaml config.yaml
cp .env.example .env
# edit config.yaml, .env, and docker-compose.yml
docker compose up -d
```

The container needs network access to your Immich server's API. The simplest approach is to run
it on the same host as Immich and attach it to Immich's compose network (see
`docker-compose.example.yml`). Alternatively, point `immich_base_url` at any URL that reaches
your server.

### CLI flags

- `--dry-run` — do everything except trash on the source; log what *would* be trashed.
- `--once` — run a single cycle and exit (otherwise polls forever).
- `--config PATH` — config file path (default `/config/config.yaml`).

## Rollout (do this before trusting real photos)

1. **Verify the API fields** on one of your albums:
   ```bash
   curl -H "x-api-key: YOUR_KEY" http://YOUR_SERVER:2283/api/albums/ALBUM_ID \
     | python -m json.tool | grep -E 'checksum|originalFileName|fileCreated'
   ```
2. **Dry run**, single cycle, against a test album:
   ```bash
   docker compose run --rm immich-cross-account-mover --once --dry-run
   ```
   Confirm the logs show the right upload/verify and the correct "would trash" candidates.
3. **Live, single cycle** with a couple of throwaway photos in the test album:
   ```bash
   docker compose run --rm immich-cross-account-mover --once
   ```
   Confirm they appear in the destination album with metadata (including GPS) looking correct
   and are trashed on the source.
4. **Enable "Sync remote deletions"** on the source phone, then start the watcher:
   ```bash
   docker compose up -d
   ```

## Development

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -v
```

The code is split into focused modules under `src/immich_cross_account_mover/`:

- `config.py` — config loading (YAML + env-injected API keys)
- `immich_client.py` — Immich API wrapper with bounded retry
- `mover.py` — the per-photo verify-before-trash state machine
- `poller.py` — the polling loop with per-asset and per-album error isolation
- `__main__.py` — CLI entrypoint (`python -m immich_cross_account_mover`)

## Releases & CI

Publishing a GitHub Release runs [`.github/workflows/release.yml`](.github/workflows/release.yml),
which:

1. Runs the full unit-test suite.
2. Only if tests pass, builds a multi-arch Docker image and pushes it to Docker Hub.

Image tags follow the release tag — use semver tags like `v1.2.3`; the workflow publishes
`{version}`, `{major}.{minor}`, and `latest`.

The image is published under the `worly` Docker Hub account (set in the workflow). The only
**required repository secret** is `DOCKERHUB_TOKEN` — a Docker Hub access token with write
scope.

## License

[MIT](LICENSE).
