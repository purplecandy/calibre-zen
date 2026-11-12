// The two shapes a dialog takes in the app. A screen says what is in one and
// never builds the Radix parts itself:
//
//   <ConfirmDialog
//     open={removing !== null}
//     onOpenChange={(o) => !o && setRemoving(null)}
//     title="Delete this file?"
//     description="It does not go to the trash."
//     confirm="Delete"
//     destructive
//     onConfirm={async () => {
//       if (await remove.run(removing)) setRemoving(null)
//     }}
//   />
//
//   <FormDialog open={open} onOpenChange={setOpen} title="Add books"
//     footer={<Button type="submit">Add</Button>} onSubmit={add}>
//     …fields…
//   </FormDialog>
import { useTransition, type ReactNode } from 'react'
import { IconLoader2 } from '@tabler/icons-react'
import { cn } from '@/lib/utils'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

/**
 * Asks before something that cannot be taken back. While `onConfirm` runs,
 * both buttons wait and the confirm button spins. The dialog does not close
 * itself: `onConfirm` closes it when the change worked, so a failure leaves
 * it open to try again.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  cancel = 'Cancel',
  confirm,
  destructive = false,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description: ReactNode
  /** Anything more to say, under the description, such as an inline error. */
  children?: ReactNode
  cancel?: string
  /** The confirm button's label, a verb: Delete, Leave, Turn off. */
  confirm: string
  destructive?: boolean
  onConfirm: () => unknown
}) {
  const [busy, start] = useTransition()
  return (
    <AlertDialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {children}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>{cancel}</AlertDialogCancel>
          <AlertDialogAction
            disabled={busy}
            variant={destructive ? 'destructive' : 'default'}
            onClick={(e) => {
              // Radix closes on Action; the caller decides instead.
              e.preventDefault()
              start(async () => {
                await onConfirm()
              })
            }}
          >
            {busy && <IconLoader2 className="animate-spin" />}
            {confirm}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

/** How wide a FormDialog is, from a short question to a long form. */
export type DialogSize = 'sm' | 'md' | 'lg' | 'xl'

const WIDTH: Record<DialogSize, string> = {
  sm: 'sm:max-w-sm',
  md: 'sm:max-w-md',
  lg: 'sm:max-w-lg',
  xl: 'sm:max-w-2xl',
}

/**
 * A dialog with a title, a description, a body and a footer of buttons.
 * With `onSubmit`, the body and footer are one form, so Enter submits and a
 * `type="submit"` button in the footer sends it.
 */
export function FormDialog({
  open,
  onOpenChange,
  title,
  description,
  size = 'lg',
  className,
  children,
  footer,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  size?: DialogSize
  /** For the content box, such as a height limit for a long list. */
  className?: string
  children?: ReactNode
  footer?: ReactNode
  onSubmit?: () => unknown
}) {
  const body = (
    <>
      {children}
      {footer && <DialogFooter>{footer}</DialogFooter>}
    </>
  )
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn(WIDTH[size], className)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? (
            <DialogDescription>{description}</DialogDescription>
          ) : (
            <DialogDescription className="sr-only">{title}</DialogDescription>
          )}
        </DialogHeader>
        {onSubmit ? (
          <form
            className="contents"
            onSubmit={(e) => {
              e.preventDefault()
              void onSubmit()
            }}
          >
            {body}
          </form>
        ) : (
          body
        )}
      </DialogContent>
    </Dialog>
  )
}
