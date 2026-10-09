# syntax=docker/dockerfile:1
#
# calibre-zen's host on a server: the web app over a library, no desktop.
#
# The same package as the Linux .txz, built the same way: packaging/linux/
# package.sh fetches calibre's own release binary for the version pinned in
# packaging/upstream.json, checks its sha256, lays this repo's src/ beside it,
# writes the launchers, precompiles and smoke-tests. Nothing is compiled from
# C. The build stage runs that script; the runtime stage copies its tree.
#
# Build from the repository root, for the machine's own architecture or for
# both (amd64 and arm64 each run their own calibre binary while building, so a
# cross build needs QEMU, which buildx sets up):
#
#   docker build -f packaging/docker/Dockerfile -t calibre-zen .
#   docker buildx build --platform linux/amd64,linux/arm64 -f packaging/docker/Dockerfile .
#
# With calibre's installer already on disk, skip the download by handing the
# build the folder that holds it (the file name and digest must match the pin):
#
#   docker build --build-context upstream=.calibre-zen/upstream ...
#
# For a local experiment only, any calibre .txz in that folder can be used
# without the version and digest checks. The result is not a release:
#
#   docker build --build-context upstream=DIR --build-arg UNPINNED_TARBALL=calibre-9.14.0-arm64.txz ...

ARG BASE=ubuntu:24.04

# Empty unless --build-context upstream=DIR replaces it.
FROM scratch AS upstream

# What calibre's Linux binary needs from the system to run with no display:
# time zones (it fails at import without them), fonts, GL and xkb stubs that
# Qt loads anyway, NSS for WebEngine. curl is for the health check.
FROM ${BASE} AS base
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        tzdata ca-certificates curl \
        libfontconfig1 libfreetype6 libegl1 libopengl0 libgl1 libxkbcommon0 \
        libglib2.0-0t64 libnss3 libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY packaging packaging
COPY resources resources
COPY src src
ARG TARGETARCH
ARG UNPINNED_TARBALL=
# The stage lands at /opt/calibre-zen, the path it has at run time.
RUN --mount=type=bind,from=upstream,target=/upstream \
    set -eu; \
    case "${TARGETARCH:-$(uname -m)}" in \
        amd64|x86_64) arch=x86_64 ;; \
        arm64|aarch64) arch=arm64 ;; \
        *) echo "unsupported architecture ${TARGETARCH:-$(uname -m)}" >&2; exit 1 ;; \
    esac; \
    mkdir -p /cache; \
    for f in /upstream/*.txz; do if [ -f "$f" ]; then ln -s "$f" /cache/; fi; done; \
    if [ -n "$UNPINNED_TARBALL" ]; then export CALIBRE_ZEN_UNPINNED_TARBALL="/upstream/$UNPINNED_TARBALL"; fi; \
    CALIBRE_ZEN_UPSTREAM_CACHE=/cache CALIBRE_ZEN_BUILD_DIR=/opt CALIBRE_ZEN_PACK=0 \
        packaging/linux/package.sh "$arch"

FROM base
COPY --from=build /opt/calibre-zen /opt/calibre-zen
COPY --chmod=755 packaging/docker/entrypoint.sh /usr/local/bin/zen-entrypoint
COPY --chmod=755 packaging/docker/healthcheck.sh /usr/local/bin/zen-healthcheck
# The folder first, at 755: BuildKit's container driver (GitHub's builder) gives
# a folder that COPY --chmod creates the file's mode, and 644 shuts PUID out.
RUN mkdir -p -m 755 /usr/local/lib/calibre-zen
COPY --chmod=644 packaging/docker/prepare.py /usr/local/lib/calibre-zen/prepare.py

# Everything the server writes goes to /config or /tmp, so the root file
# system can be mounted read-only. The entrypoint starts as root only to own
# /config, then drops to PUID:PGID.
ENV PATH=/opt/calibre-zen/zen-bin:$PATH \
    CALIBRE_CONFIG_DIRECTORY=/config \
    HOME=/config \
    XDG_CACHE_HOME=/config/cache \
    TZ=Etc/UTC \
    LANG=C.UTF-8 \
    PUID=1000 \
    PGID=1000

ARG VERSION=dev
LABEL org.opencontainers.image.title="calibre-zen" \
      org.opencontainers.image.description="calibre-zen's host: the calibre web app over your library, no desktop" \
      org.opencontainers.image.source="https://github.com/purplecandy/calibre-zen" \
      org.opencontainers.image.licenses="GPL-3.0-only" \
      org.opencontainers.image.version="${VERSION}"

VOLUME ["/config", "/library"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD ["zen-healthcheck"]
ENTRYPOINT ["zen-entrypoint"]
