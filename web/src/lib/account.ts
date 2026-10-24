// The signed-in person's own account.
import { ServerError } from './api'
import { server } from './base'

/**
 * Change the password of whoever is signed in. calibre checks the old one,
 * and refuses a new one it thinks is too weak or a user who may not change it.
 */
export async function changePassword(
  oldpw: string,
  newpw: string,
): Promise<void> {
  const res = await fetch(server('users/change-pw'), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ oldpw, newpw }),
  })
  if (!res.ok) throw new ServerError(res.status, await res.text())
}
