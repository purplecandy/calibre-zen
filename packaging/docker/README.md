# calibre-zen in Docker

This image shares your calibre library on your home server. Open it in any web browser, on a phone, tablet or computer, to find and read your books.

The image is not on `ghcr.io` yet. Until it is, build it yourself as shown at the end of this page, and use `calibre-zen` in place of `ghcr.io/purplecandy/calibre-zen:latest`.

## Start it

Make two folders, one for your books and one for settings. Then run this.

```sh
docker run -d --name calibre-zen \
  -p 8080:8080 \
  -e PUID=1000 -e PGID=1000 \
  -e CALIBRE_ZEN_USERNAME=reader -e CALIBRE_ZEN_PASSWORD=change-me \
  -v /path/to/library:/library \
  -v /path/to/config:/config \
  --restart unless-stopped \
  ghcr.io/purplecandy/calibre-zen:latest
```

Now open `http://your-server:8080` and sign in. Pick your own username and password first.

### With Docker Compose

Save this as `compose.yaml` and run `docker compose up -d` in the same folder.

```yaml
services:
  calibre-zen:
    image: ghcr.io/purplecandy/calibre-zen:latest
    container_name: calibre-zen
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      PUID: "1000"
      PGID: "1000"
      TZ: Etc/UTC
      CALIBRE_ZEN_USERNAME: reader
      CALIBRE_ZEN_PASSWORD: change-me
    volumes:
      - ./library:/library
      - ./config:/config
      - ./add-books:/auto-add
    read_only: true
    tmpfs:
      - /tmp
```

## Your books

Point `/library` at the folder that holds `metadata.db`. That is the folder calibre calls your library.

- **A library you already have.** It is served as it is. Nothing is moved or renamed.
- **A folder of libraries.** Each library inside it is served, and the web app lets you switch between them.
- **An empty folder.** A new, empty library is made there on first start.

Only one program can open a library at a time. Close calibre on other computers before you start the container on the same library.

## Adding books

Mount a folder at `/auto-add` to add books by dropping files into it. Each book you drop there is added to your library.

You can also add books from the web app once you are signed in.

## Settings

| Setting | What it does | Default |
|---|---|---|
| `PUID` and `PGID` | The user and group that own your books. Run `id` on the server to find yours. | `1000` |
| `CALIBRE_ZEN_USERNAME` | Turns on sign in, with this user. | none |
| `CALIBRE_ZEN_PASSWORD` | The password for that user. | none |
| `CALIBRE_ZEN_PASSWORD_FILE` | Reads the password from a file instead, such as a Docker secret. | none |
| `CALIBRE_ZEN_TRUSTED_IPS` | Lets these addresses add and change books without signing in, for example `192.168.1.0/24`. | none |
| `CALIBRE_ZEN_URL_PREFIX` | Serves the app under a path, such as `/books`, behind a reverse proxy. | none |
| `CALIBRE_ZEN_PORT` | The port inside the container. Handy with host networking. | `8080` |
| `TZ` | Your time zone, such as `Europe/Berlin`. | `Etc/UTC` |
| `UMASK` | The permissions new files get. Use `002` to share a library with a group. | `022` |

| Folder | What goes there |
|---|---|
| `/library` | Your calibre library, or an empty folder for a new one. |
| `/config` | Settings, users and a cache of covers. Keep it between updates. |
| `/auto-add` | Optional. Books dropped here are added to the library. |

## Signing in and making changes

With a username and password set, everyone signs in first. People who sign in can read, add and edit books.

Without a username, anyone who can reach the server can read your books. Changes stay off until you set a username or list trusted addresses. Your users and their passwords live in `/config`. Delete `server-users.sqlite` there to turn sign in off again.

## More options

Anything after the image name goes to the server as an extra option. For example, `--auth-mode basic` suits a reverse proxy that adds HTTPS.

The server never runs as root. It starts as root only to give `/config` to your user, then switches to `PUID` and `PGID`. You can also start it with `--user 1000:1000` if you set up the folders yourself.

## Updating

Pull the new image and start the container again. Your books and settings stay in the folders you mounted.

```sh
docker pull ghcr.io/purplecandy/calibre-zen:latest
docker rm -f calibre-zen
```

Then run the same `docker run` line as before, or `docker compose up -d`.

## Building the image yourself

From the top of the calibre-zen source, run this. It downloads calibre's own Linux release and checks it before use.

```sh
docker build -f packaging/docker/Dockerfile -t calibre-zen .
```
