# calibre-zen in Docker

This image shares your calibre library on your home server. Open it in any web browser, on a phone, tablet or computer, to find and read your books.

The image is `ghcr.io/purplecandy/calibre-zen`, for Intel and ARM servers alike.

- **`latest`** is the newest release, and the steady choice.
- **`edge`** has the newest changes as soon as they are made, so it can have rough edges.
- **A version**, such as `0.4.0` or `0.4`, stays on that release.

## Start it

Make two folders, one for your books and one for settings. Then run this.

```sh
docker run -d --name calibre-zen \
  -p 8080:8080 \
  -e PUID=1000 -e PGID=1000 \
  -e CALIBRE_ZEN_USERNAME=reader -e CALIBRE_ZEN_PASSWORD=PICK-A-PASSWORD \
  -v /path/to/library:/library \
  -v /path/to/config:/config \
  --restart unless-stopped \
  ghcr.io/purplecandy/calibre-zen:latest
```

Put your own password in place of `PICK-A-PASSWORD` first. The image will not start with that placeholder. Then open `http://your-server:8080` and sign in.

### With Docker Compose

The compose file comes down with one line, best run in a new folder:

```sh
curl -fsSLO https://raw.githubusercontent.com/purplecandy/calibre-zen/zen/packaging/docker/compose.yaml
```

Your password goes next to it, in a file named `.env` with one line, `CALIBRE_ZEN_PASSWORD=` and then the password. `docker compose up -d` in that folder starts it. The file holds this:

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
      CALIBRE_ZEN_PASSWORD: ${CALIBRE_ZEN_PASSWORD:?put CALIBRE_ZEN_PASSWORD in a .env file next to compose.yaml}
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

The container must be able to write to your library, even just to show it. Do not mount it read-only, and make sure `PUID` owns the books. If it cannot write, it stops and tells you why.

Keep your library out of `/config`. Some other calibre images keep it there. If you come from one of those, mount the library folder at `/library` and give `/config` a new, empty folder.

## Adding books

Mount a folder at `/auto-add` to add books by dropping files into it. Each book you drop there is added to your library.

The folder must be one that `PUID` can write to. A new, empty folder is set up for you on first start. If the folder cannot be used, the log says so and the rest still works.

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

## More users

`CALIBRE_ZEN_USERNAME` sets up one user. To add more, or to change or remove one, run this while the container is up. It shows a menu.

```sh
docker exec -it calibre-zen zen-entrypoint --manage-users
```

You can also do it in one line. Leave out the password and you are asked for it.

```sh
docker exec -it calibre-zen zen-entrypoint --manage-users -- add bob
docker exec calibre-zen zen-entrypoint --manage-users -- list
```

Changes work right away. If these are your first users, restart the container to turn sign in on.

## More options

Anything after the image name goes to the server as an extra option. For example, `--auth-mode basic` suits a reverse proxy that adds HTTPS. To serve HTTPS yourself, mount your certificate and add `--ssl-certfile` and `--ssl-keyfile`.

The server never runs as root. It starts as root only to give `/config` and any new, empty folders to your user, then switches to `PUID` and `PGID`. You can also start it with `--user 1000:1000` if you set up the folders yourself.

## Updating

An update is the new image pulled and the container started again. Your books and settings stay in the folders you mounted. With Compose, `docker compose pull && docker compose up -d` does both.

```sh
docker pull ghcr.io/purplecandy/calibre-zen:latest
docker rm -f calibre-zen
```

Then run the same `docker run` line as before, or `docker compose up -d`.

## Building the image yourself

The images on `ghcr.io` are built this way, and each one is started and tried before it is published. The same build works from the top of the calibre-zen source. It downloads calibre's own Linux release and checks it before use.

```sh
docker build -f packaging/docker/Dockerfile -t calibre-zen .
```
