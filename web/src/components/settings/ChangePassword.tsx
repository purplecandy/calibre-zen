// Change the signed-in person's password, through calibre's /users/change-pw.
// The browser keeps the old password for this server and does not know the
// new one, so it asks for the login again on the next request.
//
// The dialog is mounted once, by its provider in AppProviders. Anything that
// offers the change -- the app menu, the Settings page -- asks for it with
// useChangePassword(). A menu item cannot hold the dialog itself: the menu
// closes as the item is chosen, and the dialog would close with it.
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import { changePassword, PASSWORD_ERRORS } from '@/lib/account'
import { useAction } from '@/lib/action'
import { useOnline } from '@/lib/hooks'
import { useServerInfo } from '@/lib/queries'
import { FormDialog } from '@/components/app/Dialogs'
import { Field } from '@/components/app/Field'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

const OpenChangePassword = createContext<(() => void) | null>(null)

/** Opens the Change password dialog. Only offer it to someone signed in. */
export function useChangePassword(): () => void {
  const open = useContext(OpenChangePassword)
  if (!open) throw new Error('useChangePassword needs a ChangePasswordProvider')
  return open
}

export function ChangePasswordProvider({ children }: { children: ReactNode }) {
  const user = useServerInfo().username
  const [open, setOpen] = useState(false)
  const show = useCallback(() => setOpen(true), [])
  return (
    <OpenChangePassword value={show}>
      {children}
      {user && (
        <FormDialog
          open={open}
          onOpenChange={setOpen}
          title="Change password"
          description={`For ${user} on this server.`}
          size="sm"
        >
          {/* Mounted only while open, so it starts empty every time. */}
          <PasswordForm />
        </FormDialog>
      )}
    </OpenChangePassword>
  )
}

function PasswordForm() {
  const online = useOnline()
  const [oldpw, setOld] = useState('')
  const [newpw, setNew] = useState('')
  const [again, setAgain] = useState('')
  const [mismatch, setMismatch] = useState(false)
  const [done, setDone] = useState(false)
  const change = useAction({
    run: () => changePassword(oldpw, newpw).then(() => true),
    failure: 'inline',
    wording: PASSWORD_ERRORS,
  })
  const error = mismatch
    ? 'The two new passwords are not the same.'
    : change.error

  const submit = async () => {
    setMismatch(newpw !== again)
    if (newpw !== again) return
    if (await change.run()) setDone(true)
  }

  if (done) {
    return (
      <>
        <p className="text-sm">
          Your password is changed. Your browser will ask you to sign in again
          with the new one.
        </p>
        <DialogFooter>
          <Button onClick={() => location.reload()}>Sign in again</Button>
        </DialogFooter>
      </>
    )
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        void submit()
      }}
      className="grid gap-4"
    >
      <Field label="Current password" id="pw-old">
        <Input
          id="pw-old"
          type="password"
          autoComplete="current-password"
          value={oldpw}
          onChange={(e) => setOld(e.target.value)}
          required
        />
      </Field>
      <Field label="New password" id="pw-new">
        <Input
          id="pw-new"
          type="password"
          autoComplete="new-password"
          value={newpw}
          onChange={(e) => setNew(e.target.value)}
          required
        />
      </Field>
      <Field label="New password again" id="pw-again">
        <Input
          id="pw-again"
          type="password"
          autoComplete="new-password"
          value={again}
          onChange={(e) => setAgain(e.target.value)}
          required
        />
      </Field>
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
        <Button type="submit" disabled={change.busy || !online}>
          Change password
        </Button>
      </DialogFooter>
    </form>
  )
}
