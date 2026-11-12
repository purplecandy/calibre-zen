// The signed-in person's own account.
import { UNREACHABLE, type Wording } from './errors'
import { post } from './http'

/**
 * Change the password of whoever is signed in. calibre checks the old one,
 * and refuses a new one it thinks is too weak or a user who may not change it.
 */
export function changePassword(oldpw: string, newpw: string): Promise<void> {
  return post('users/change-pw', { oldpw, newpw }, { as: 'none' })
}

/** What to tell someone whose password was not changed. */
export const PASSWORD_ERRORS: Wording = {
  status: {
    403: 'This account cannot change its password here. The person who runs the server can change it.',
  },
  server: (e) => e.message || 'The password was not changed.',
  other: UNREACHABLE,
}
