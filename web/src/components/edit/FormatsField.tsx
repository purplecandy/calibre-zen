// A book's files in the editor: take one away, or add another format.
// Saved with the rest of the form, through set-fields, as calibre's app does.
import { useRef } from 'react'
import { IconArrowBackUp, IconPlus, IconX } from '@tabler/icons-react'
import { formatSize } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

export interface FormatChanges {
  removed: string[]
  added: File[]
}

export const extension = (f: File) =>
  f.name.includes('.') ? f.name.split('.').pop()!.toUpperCase() : ''

export function FormatsField({
  formats,
  sizes,
  value,
  onChange,
}: {
  formats: string[]
  sizes: Record<string, number>
  value: FormatChanges
  onChange: (v: FormatChanges) => void
}) {
  const picker = useRef<HTMLInputElement>(null)
  const toggle = (fmt: string) =>
    onChange({
      ...value,
      removed: value.removed.includes(fmt)
        ? value.removed.filter((x) => x !== fmt)
        : [...value.removed, fmt],
    })

  return (
    <div className="flex flex-col gap-1.5">
      <ul className="flex flex-col gap-1 text-sm">
        {formats.map((fmt) => {
          const gone = value.removed.includes(fmt)
          return (
            <li key={fmt} className="flex items-center gap-2">
              <span
                className={cn(
                  'font-medium',
                  gone && 'text-muted-foreground line-through',
                )}
              >
                {fmt}
              </span>
              <span className="text-xs text-muted-foreground">
                {gone ? 'removed on save' : formatSize(sizes[fmt])}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="ml-auto size-7"
                aria-label={gone ? `Keep ${fmt}` : `Remove ${fmt}`}
                onClick={() => toggle(fmt)}
              >
                {gone ? <IconArrowBackUp /> : <IconX />}
              </Button>
            </li>
          )
        })}
        {value.added.map((f, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="font-medium">{extension(f)}</span>
            <span className="truncate text-xs text-muted-foreground">
              added on save
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="ml-auto size-7"
              aria-label={`Do not add ${f.name}`}
              onClick={() =>
                onChange({
                  ...value,
                  added: value.added.filter((_, j) => j !== i),
                })
              }
            >
              <IconX />
            </Button>
          </li>
        ))}
      </ul>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => picker.current?.click()}
      >
        <IconPlus />
        Add a format
      </Button>
      <input
        ref={picker}
        type="file"
        multiple
        hidden
        aria-label="Book files to add"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []).filter(extension)
          if (files.length)
            onChange({ ...value, added: [...value.added, ...files] })
          e.target.value = ''
        }}
      />
    </div>
  )
}
