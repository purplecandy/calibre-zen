// A text box that suggests what the library already has: authors, tags,
// series, publishers, a column's values. A plain input with a list under it,
// keyboard first, so it behaves the same in a form, on a phone and in a
// dialog.
import {
  useId,
  useMemo,
  useState,
  type ComponentProps,
  type KeyboardEvent,
} from 'react'
import { useFieldNames } from '@/lib/edit-queries'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover'

const SHOWN = 8

/** Values starting with `text` first, then those containing it. */
export function match(
  names: readonly string[],
  text: string,
  skip: ReadonlySet<string>,
): string[] {
  const q = text.trim().toLowerCase()
  if (!q) return []
  const starts: string[] = []
  const contains: string[] = []
  for (const n of names) {
    if (skip.has(n)) continue
    const l = n.toLowerCase()
    if (l === q) continue
    if (l.startsWith(q)) starts.push(n)
    else if (contains.length < SHOWN && l.includes(q)) contains.push(n)
    if (starts.length >= SHOWN) break
  }
  return [...starts, ...contains].slice(0, SHOWN)
}

interface Props extends Omit<
  ComponentProps<typeof Input>,
  'value' | 'onChange'
> {
  library: string
  field: string
  value: string
  onChange: (text: string) => void
  /** A suggestion was chosen. Without it, choosing one sets the text. */
  onPick?: (name: string) => void
  /** Values not to suggest, such as the tags already there. */
  skip?: ReadonlySet<string>
  /** Whether to suggest at all. */
  suggest?: boolean
}

export function Suggest({
  library,
  field,
  value,
  onChange,
  onPick,
  skip,
  suggest = true,
  onKeyDown,
  onFocus,
  onBlur,
  className,
  ...props
}: Props) {
  const [focused, setFocused] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const names = useFieldNames(library, field, suggest && focused)
  const list = useMemo(
    () => match(names.data ?? [], value, skip ?? new Set()),
    [names.data, value, skip],
  )
  const id = useId()
  const shown = open && focused && list.length > 0

  const pick = (name: string) => {
    if (onPick) onPick(name)
    else onChange(name)
    setOpen(false)
    setActive(-1)
  }

  const keys = (e: KeyboardEvent<HTMLInputElement>) => {
    if (shown) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const step = e.key === 'ArrowDown' ? 1 : -1
        setActive((a) => {
          const n = a + step
          return n >= list.length ? -1 : n < -1 ? list.length - 1 : n
        })
        return
      }
      if (e.key === 'Enter' && active >= 0 && active < list.length) {
        e.preventDefault()
        pick(list[active])
        return
      }
      if (e.key === 'Escape') {
        // Closes the list, not the dialog it is in.
        e.preventDefault()
        e.stopPropagation()
        setOpen(false)
        return
      }
    } else if (e.key === 'ArrowDown' && list.length) {
      e.preventDefault()
      setOpen(true)
      setActive(0)
      return
    }
    onKeyDown?.(e)
  }

  return (
    <Popover open={shown} onOpenChange={(o) => !o && setOpen(false)}>
      <PopoverAnchor asChild>
        <div className={className}>
          <Input
            {...props}
            value={value}
            role="combobox"
            aria-expanded={shown}
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
            aria-activedescendant={
              shown && active >= 0 && active < list.length
                ? `${id}-${active}`
                : undefined
            }
            autoComplete="off"
            onChange={(e) => {
              onChange(e.target.value)
              setOpen(true)
              setActive(-1)
            }}
            onFocus={(e) => {
              setFocused(true)
              onFocus?.(e)
            }}
            onBlur={(e) => {
              setFocused(false)
              setOpen(false)
              onBlur?.(e)
            }}
            onKeyDown={keys}
          />
        </div>
      </PopoverAnchor>
      <PopoverContent
        align="start"
        // The focus stays in the text box while the list is open.
        onOpenAutoFocus={(e) => e.preventDefault()}
        onCloseAutoFocus={(e) => e.preventDefault()}
        className="max-h-64 w-auto max-w-[min(24rem,90vw)] min-w-[max(var(--radix-popper-anchor-width),14rem)] overflow-y-auto p-1"
      >
        <ul id={`${id}-list`} role="listbox" className="text-sm">
          {list.map((name, i) => (
            <li
              key={name}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === active}
              className={cn(
                'cursor-default truncate rounded-sm px-2 py-1.5',
                i === active && 'bg-accent text-accent-foreground',
              )}
              // Keep the focus in the box, so blur does not close the list first.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(name)}
              onMouseEnter={() => setActive(i)}
            >
              {name}
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  )
}
