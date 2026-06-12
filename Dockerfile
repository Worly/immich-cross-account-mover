FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
# slim (Debian Bookworm) ships no C toolchain; the runtime deps
# (httpx, pydantic, pyyaml) all provide prebuilt arm64 wheels, so this
# installs without a compiler. If a future dep lacks an arm64 wheel,
# add build-essential here or switch off slim.
RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "immich_cross_account_mover"]
CMD ["--config", "/config/config.yaml"]
