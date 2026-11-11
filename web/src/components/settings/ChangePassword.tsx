// Change the signed-in person's password, through calibre's /users/change-pw.
// The browser keeps the old password for this server and does not know the
// new one, so it asks for the login again on the next request.
import { useState, useSyncExternalStore } from 'react'
import { changePassword } from '@/lib/account'
import { ServerError } from '@/lib/api'
import { useOnline } from '@/lib/offline'
import { useServerInfo } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

// Open from anywhere: a menu item closes its menu as it is chosen, so the
// dialog cannot live inside the menu.
let isOpen = false
const listeners = new Set<() => void>()

function setOpen(open: boolean) {
  isOpen = open
  listeners.forEach((f) => f())
}

export function openChangePassword() {
  setOpen(true)
}

function subscribe(f: () => void) {
  listeners.add(f)
  return () => listeners.delete(f)
}

/** The dialog, once per page (AppProviders). Shown only to someone signed in. */
export function ChangePassword() {
  const user = useServerInfo().data?.username
  const open = useSyncExternalStore(subscribe, () => isOpen)
  const online = useOnline()
  const [oldpw, setOld] = useState('')
  const [newpw, setNew] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const reset = () => {
    setOld('')
    setNew('')
    setAgain('')
    setError('')
    setDone(false)
  }

  const submit = async () => {
    if (newpw !== again) {
      setError('The two new passwords are not the same.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await changePassword(oldpw, newpw)
      setDone(true)
    } catch (err) {
      setError(
        err instanceof ServerError
          ? err.status === 403
            ? 'This account cannot change its password here. The person who runs the server can change it.'
            : err.message || 'The password was not changed.'
          : 'The server could not be reached.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (!user) return null
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) reset()
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Change password</DialogTitle>
          <DialogDescription>For {user} on this server.</DialogDescription>
        </DialogHeader>
        {done ? (
          <>
            <p className="text-sm">
              Your password is changed. Your browser will ask you to sign in
              again with the new one.
            </p>
            <DialogFooter>
              <Button onClick={() => location.reload()}>Sign in again</Button>
            </DialogFooter>
          </>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
            className="grid gap-4"
          >
            <div className="grid gap-2">
              <Label htmlFor="pw-old">Current password</Label>
              <Input
                id="pw-old"
                type="password"
                autoComplete="current-password"
                value={oldpw}
                onChange={(e) => setOld(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="pw-new">New password</Label>
              <Input
                id="pw-new"
                type="password"
                autoComplete="new-password"
                value={newpw}
                onChange={(e) => setNew(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="pw-again">New password again</Label>
              <Input
                id="pw-again"
                type="password"
                autoComplete="new-password"
                value={again}
                onChange={(e) => setAgain(e.target.value)}
                required
              />
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            {!online && (
              <p className="text-sm text-muted-foreground">
                You can change it once you are back online.
              </p>
            )}
            <DialogFooter>
              <Button type="submit" disabled={busy || !online}>
                Change password
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
