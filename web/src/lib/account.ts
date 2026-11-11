// The signed-in person's own account.
import { post } from './http'

/**
 * Change the password of whoever is signed in. calibre checks the old one,
 * and refuses a new one it thinks is too weak or a user who may not change it.
 */
export function changePassword(oldpw: string, newpw: string): Promise<void> {
  return post('users/change-pw', { oldpw, newpw }, { as: 'none' })
}
