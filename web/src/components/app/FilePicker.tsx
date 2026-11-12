// Choosing files: a click on the child opens the browser's file picker, and
// with `drop` the child also takes files dropped on it. The child is any
// element, a button or a drop zone, and is marked `data-over` while files
// are dragged over it, for its own styling:
//
//   <FilePicker label="Book files" multiple drop onPick={queue}>
//     <button className="… data-[over]:border-ring">Drop files here</button>
//   </FilePicker>
//
// The hidden input keeps `label` as its name, which is what a test sets
// files on.
import { useRef, useState, type DragEvent, type ReactNode } from 'react'
import { Slot } from 'radix-ui'

export function FilePicker({
  label,
  accept,
  multiple = false,
  drop = false,
  onPick,
  children,
}: {
  /** What the files are for, such as "Book files". The input's name. */
  label: string
  /** Which files to offer, as in <input accept>, such as "image/*". */
  accept?: string
  multiple?: boolean
  /** Also take files dropped on the child. */
  drop?: boolean
  /** The files chosen or dropped. Never called with none. */
  onPick: (files: File[]) => void
  children: ReactNode
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  const pick = (list: FileList | null | undefined) => {
    const files = Array.from(list ?? []).filter((f) => fits(f, accept))
    if (files.length) onPick(multiple ? files : files.slice(0, 1))
  }

  const dropping = drop
    ? {
        'data-over': over ? '' : undefined,
        onDragOver: (e: DragEvent) => {
          e.preventDefault()
          setOver(true)
        },
        onDragLeave: () => setOver(false),
        onDrop: (e: DragEvent) => {
          e.preventDefault()
          setOver(false)
          pick(e.dataTransfer.files)
        },
      }
    : {}

  return (
    <>
      <Slot.Root onClick={() => input.current?.click()} {...dropping}>
        {children}
      </Slot.Root>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        aria-label={label}
        onChange={(e) => {
          pick(e.target.files)
          // So the same file can be chosen again.
          e.target.value = ''
        }}
      />
    </>
  )
}

/** Whether a dropped file is one the picker would have offered. */
function fits(file: File, accept: string | undefined): boolean {
  if (!accept) return true
  return accept.split(',').some((a) => {
    const t = a.trim()
    if (t.startsWith('.')) return file.name.toLowerCase().endsWith(t)
    if (t.endsWith('/*')) return file.type.startsWith(t.slice(0, -1))
    return file.type === t
  })
}
