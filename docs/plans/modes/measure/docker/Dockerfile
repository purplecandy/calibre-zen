# Stock calibre-server on Linux, for measuring only. Not the product image.
# The build context holds calibre/, an extracted calibre-<version>-<arch>.txz;
# measure-docker.sh prepares it.
FROM ubuntu:24.04
# What calibre's Linux binary needs from the system to run headless: time
# zones, fonts, GL and xkb stubs that Qt loads even with no display, and NSS
# for WebEngine.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        tzdata libfontconfig1 libfreetype6 libegl1 libopengl0 libgl1 libxkbcommon0 \
        libglib2.0-0t64 libnss3 libdbus-1-3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY calibre /opt/calibre
# ubuntu:24.04 ships the user "ubuntu" as uid 1000
USER ubuntu
EXPOSE 8080
ENTRYPOINT ["/opt/calibre/calibre-server", "--port", "8080", "--disable-use-bonjour"]
