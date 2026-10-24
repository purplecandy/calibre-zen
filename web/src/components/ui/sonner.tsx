import { useSyncExternalStore, type CSSProperties } from 'react'
import {
  IconAlertOctagon,
  IconAlertTriangle,
  IconCircleCheck,
  IconInfoCircle,
  IconLoader2,
} from '@tabler/icons-react'
import { Toaster as Sonner, type ToasterProps } from 'sonner'

// shadcn's version asks next-themes for the theme. Here it is the `dark`
// class lib/appearance.ts puts on <html>, watched for changes.
function subscribe(f: () => void) {
  const o = new MutationObserver(f)
  o.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class'],
  })
  return () => o.disconnect()
}

const isDark = () => document.documentElement.classList.contains('dark')

const Toaster = ({ ...props }: ToasterProps) => {
  const dark = useSyncExternalStore(subscribe, isDark)

  return (
    <Sonner
      theme={dark ? 'dark' : 'light'}
      className="toaster group"
      icons={{
        success: <IconCircleCheck className="size-4" />,
        info: <IconInfoCircle className="size-4" />,
        warning: <IconAlertTriangle className="size-4" />,
        error: <IconAlertOctagon className="size-4" />,
        loading: <IconLoader2 className="size-4 animate-spin" />,
      }}
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
          '--border-radius': 'var(--radius)',
        } as CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
