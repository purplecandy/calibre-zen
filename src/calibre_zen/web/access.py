#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
GET /zen/api/can-edit?library_id=...: whether this request may change the
library, and if not, why.

calibre's own web app does not ask. It shows every editing control and lets
the server refuse with a 403 on click. The new app hides or disables them up
front and says why, so it needs to know before anything is clicked.

The answer follows calibre's rules exactly, by asking calibre:

    anonymous    no one is signed in, and this request is not from a trusted
                 address (--local-write from this computer, --trusted-ips).
                 What a server without --enable-auth is, for everyone else
    read-only    the signed-in user is read-only
    restricted   the user sees only part of this library. calibre's
                 set-fields, add, delete, cover and copy endpoints all refuse
                 such a user, so the app treats the library as read-only

The route needs the login like the rest of the data, and is added beside
/app/ by serve.install.
"""

ROUTE = '/zen/api/can-edit'


def can_edit(ctx, rd, db) -> tuple[bool, str]:
    from calibre.srv.errors import HTTPForbidden

    try:
        ctx.check_for_write_access(rd)
    except HTTPForbidden:
        return False, ('read-only' if rd.username else 'anonymous')
    if db is not None and ctx.restriction_for(rd, db):
        return False, 'restricted'
    return True, ''


def make_route():
    from calibre.srv.routes import endpoint, json
    from calibre.srv.utils import get_library_data

    @endpoint(ROUTE, postprocess=json, cache_control='no-cache')
    def zen_api_can_edit(ctx, rd):
        db = get_library_data(ctx, rd)[0]
        ok, reason = can_edit(ctx, rd, db)
        return {'can_edit': ok, 'reason': reason}

    return zen_api_can_edit
