#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
GET /zen/status and POST /zen/stop, and what they answer.

How they get into the server: calibre's Handler loads its route modules and
the content-server plugins' routes, then calls Router.finalize(), which only
builds lookup tables from Router.routes. `install` adds two more routes with
the public Router.add and finalizes again. No calibre method is wrapped, so
nothing here can be undone by a change to how calibre loads its routes, and
calibre's own routes are already in place, so ours cannot shadow one. A
plugin cannot take /zen either: plugins are loaded first, and Router.add
refuses a key that is already there.

Both routes skip calibre's login check and make their own:

    /zen/status   the full answer for a request that carries the host's
                  secret (secret.py), or a login when --enable-auth is on.
                  Anyone else gets only that the host is up, which is all
                  Docker's health check needs, and never a 401. To log in,
                  ask for /zen/status?full=1, or send the login with the
                  request: digest clients such as curl send one only after
                  a 401, which ?full=1 gives them.
    /zen/stop     the secret, and from this computer, and not a browser page
                  from another site (see `cross_site`). 403 otherwise.

A request is from "this computer" when all three hold:

    the peer      a loopback address, or one of this computer's own interface
                  addresses -- a host listening on one LAN address sees the
                  tray arrive from that address, not from 127.0.0.1
    no proxy      no X-Forwarded-For, Forwarded or X-Real-IP header. Through
                  a proxy the proxy is local and the person is not
    the Host      what the client asked for is this computer by number, or
                  `localhost`: 127.0.0.1, [::1], an own address, with or
                  without a port. This stops DNS rebinding: a page on
                  evil.example whose name is pointed at 127.0.0.1 arrives
                  from loopback with a matching Origin, but its Host is still
                  evil.example. It also stops a reverse proxy on this
                  computer that forwards the public name and adds no header

The tray and launch.py ask by number, so they pass. A browser on this
computer that uses the machine's name (mymac.local) is treated as anyone
else. A proxy that rewrites Host to 127.0.0.1 and adds no forwarding header
still looks local, and nothing in the request can tell it apart from the
tray. That is what the secret is for: the proxy's visitors cannot read it.
"""

import ipaddress
import os
import time
from threading import Lock
from urllib.parse import urlsplit

from calibre.srv.errors import HTTPForbidden
from calibre.srv.routes import endpoint, json
from calibre_zen.host import secret

ADDRESS_CACHE_SECONDS = 30
_cache_lock = Lock()
_cache: dict[str, tuple[float, object]] = {}


def cached(key: str, compute):
    "compute(), remembered for ADDRESS_CACHE_SECONDS. Interfaces change, but not per request."
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and now - hit[0] < ADDRESS_CACHE_SECONDS:
            return hit[1]
    value = compute()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


# Who is asking {{{


def own_addresses() -> frozenset:
    "Every address on this computer's interfaces, IPv4 and IPv6."

    def compute():
        ans = set()
        try:
            import netifaces  # type: ignore
        except ImportError:
            return frozenset()
        for family in ('AF_INET', 'AF_INET6'):
            fam = getattr(netifaces, family, None)
            if fam is None:
                continue
            for iface in netifaces.interfaces():
                try:
                    entries = netifaces.ifaddresses(iface).get(fam, ())
                except ValueError:
                    continue
                for entry in entries:
                    addr = (entry.get('addr') or '').partition('%')[0]  # drop an IPv6 zone
                    try:
                        ans.add(ipaddress.ip_address(addr))
                    except ValueError:
                        pass
        return frozenset(ans)

    return cached('own', compute)


# Headers a proxy adds to say who it is passing a request on for. calibre
# itself reads only the first (rd.forwarded_for). As calibre spells them:
# http_request.normalize_header_name capitalizes each part.
PROXY_HEADERS = ('X-Forwarded-For', 'Forwarded', 'X-Real-Ip')


def own_ip(text) -> bool:
    "Whether `text` is an IP address of this computer: loopback or an interface's."
    try:
        addr = ipaddress.ip_address(str(text or '').partition('%')[0])
    except ValueError:
        return False
    addr = getattr(addr, 'ipv4_mapped', None) or addr
    if addr.is_loopback:
        return True
    return addr in own_addresses()


def is_this_computer(remote_addr, forwarded_for=None) -> bool:
    "Whether the peer is this computer and not a proxy speaking for someone."
    if forwarded_for:
        return False
    return own_ip(remote_addr)


def host_is_this_computer(host: str | None) -> bool:
    """
    Whether a Host header names this computer: `localhost`, or one of its
    addresses as a literal, each with or without a port. Not a host name
    that resolves here -- that is what DNS rebinding forges.
    """
    host = (host or '').strip()
    if not host:
        return False
    if own_ip(host):  # a bare IPv6 address, which a client should bracket but may not
        return True
    try:
        parts = urlsplit('//' + host)
        port = parts.port  # ValueError for a port that is not a number
    except ValueError:
        return False
    if port == 0 or parts.username is not None or parts.path or parts.query or parts.fragment:
        return False
    name = parts.hostname or ''
    return name == 'localhost' or own_ip(name)


def cross_site(origin: str | None, host: str | None) -> bool:
    """
    Whether a browser sent this request from a page on another site.

    Any web page can make a browser POST to 127.0.0.1 without asking, and the
    request then arrives from this computer. A browser always says where such
    a request comes from in Origin; curl, urllib and the tray do not send one.
    So a request whose Origin is not this server is refused.
    """
    if not origin:
        return False
    if origin == 'null':
        return True
    return urlsplit(origin).netloc.lower() != (host or '').lower()


def request_is_local(rd) -> bool:
    "Whether a request comes from this computer, by the three rules above."
    if any(rd.inheaders.get(name) for name in PROXY_HEADERS):
        return False
    return is_this_computer(rd.remote_addr, rd.forwarded_for) and host_is_this_computer(rd.inheaders.get('Host'))


# }}}

# Routes {{{


@endpoint('/zen/status', auth_required=False, postprocess=json, cache_control='no-cache')
def zen_status(ctx, rd):
    """
    The host's state as JSON: versions, uptime, where it is shared, the
    libraries, jobs, the watched folder and memory. See first-cut.md.
    """
    host = ctx.zen_host
    if has_secret(rd, host):
        return host.status()
    if host.auth_controller is not None and (rd.inheaders.get('Authorization') or rd.query.get('full')):
        host.auth_controller(rd, zen_status)  # a 401 challenge, or a wrong login refused
        return host.status()
    return host.brief()


@endpoint('/zen/stop', methods=('POST',), auth_required=False, postprocess=json, cache_control='no-cache', ok_code=200)
def zen_stop(ctx, rd):
    "Stop the host. From this computer only, with the host's secret."
    if not has_secret(rd, ctx.zen_host) or not request_is_local(rd) or cross_site(rd.inheaders.get('Origin'), rd.inheaders.get('Host')):
        raise HTTPForbidden('Only this computer can stop calibre-zen', log=f'Refused /zen/stop from {rd.remote_addr}')
    ctx.zen_host.stop_soon()
    return {'stopping': True}


ROUTES = (zen_status, zen_stop)


def has_secret(rd, host) -> bool:
    return secret.matches(getattr(host, 'secret', ''), rd.inheaders.get(secret.HEADER))


def install(router) -> None:
    "Add the routes to a router calibre has already finalized, and finalize it again."
    for route in ROUTES:
        router.add(route)
    router.finalize()


# }}}

# What /zen/status says {{{


def lan_addresses() -> list[str]:
    """
    The addresses another device on the network would use: the one the
    default route leaves from first -- what Preferences -> Sharing and the
    main window's Connect/share menu show -- then any other interface on a
    broadcast network. Loopback and point-to-point links are left out.
    """

    def compute():
        ans = []
        try:
            from calibre.utils.ip_routing import get_default_route_src_address

            first = get_default_route_src_address()
        except Exception:
            first = None
        if first:
            ans.append(first)
        try:
            import netifaces  # type: ignore

            for iface in netifaces.interfaces():
                for entry in netifaces.ifaddresses(iface).get(netifaces.AF_INET, ()):
                    addr = entry.get('addr')
                    if addr and entry.get('broadcast') and not addr.startswith('127.') and addr not in ans:
                        ans.append(addr)
        except Exception:
            pass
        return ans

    return list(cached('lan', compute))


def share_urls(opts, port: int) -> list[str]:
    from calibre.utils.network import format_addr_for_url
    from calibre_zen.host.options import ANY_ADDRESS

    scheme = 'https' if opts.ssl_certfile and opts.ssl_keyfile else 'http'
    prefix = (opts.url_prefix or '').rstrip('/')
    if prefix and not prefix.startswith('/'):
        prefix = '/' + prefix
    listen_on = (opts.listen_on or '').strip()
    if listen_on in ANY_ADDRESS:
        addrs = lan_addresses()
    else:
        try:
            ip = ipaddress.ip_address(listen_on)
        except ValueError:
            addrs = [listen_on]  # a host name
        else:
            addrs = [] if ip.is_loopback else [listen_on]
    return [f'{scheme}://{format_addr_for_url(a)}:{port}{prefix}/' for a in addrs]


def libraries(broker) -> list[dict]:
    with broker:
        lmap = list(broker.lmap.items())
        names = dict(broker.library_name_map)
        paths = dict(broker.original_path_map)
        loaded = dict(broker.loaded_dbs)
    ans = []
    for library_id, path in lmap:
        db = loaded.get(library_id)
        books = None
        if db is not None:
            try:
                books = len(db.new_api.all_book_ids())
            except Exception:
                books = None
        ans.append({
            'id': library_id,
            'name': names.get(library_id, library_id),
            'path': os.path.normpath(paths.get(path, path)),
            'open': db is not None,
            'books': books,
        })
    return ans


def jobs(jobs_manager) -> dict:
    # JobsManager has no public list. Its two collections, read under its lock:
    # jobs is the running ones, waiting_job_ids the ones queued behind
    # max_jobs. Finished jobs move to finished_jobs and are not counted.
    if jobs_manager is None:
        return {'running': 0, 'waiting': 0}
    with jobs_manager.lock:
        return {'running': len(jobs_manager.jobs), 'waiting': len(jobs_manager.waiting_job_ids)}


def memory_mb() -> float | None:
    "Resident memory, in MB."
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / 2**20, 1)
    except Exception:
        pass
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        from calibre.constants import ismacos

        return round(peak / 2**20 if ismacos else peak / 2**10, 1)  # bytes on macOS, KB on Linux
    except Exception:
        return None


# }}}
