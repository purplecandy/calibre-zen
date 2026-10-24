// The cover in the editor: the one the book has, a new picture chosen or
// dropped on it, or none. Nothing is sent until the form is saved.
import { useEffect, useRef, useState } from 'react'
import { IconPhotoUp, IconTrash } from '@tabler/icons-react'
import type { Book } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Cover } from '@/components/library/Cover'

/** null keeps the cover, 'remove' takes it away, a file replaces it. */
export type CoverChange = null | 'remove' | File

export function CoverField({
  library,
  book,
  value,
  onChange,
}: {
  library: string
  book: Book & { id: number }
  value: CoverChange
  onChange: (c: CoverChange) => void
}) {
  const picker = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)

  useEffect(() => {
    if (!(value instanceof File)) return setPreview(null)
    const url = URL.createObjectURL(value)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [value])

  const take = (files: FileList | null | undefined) => {
    const f = Array.from(files ?? []).find((x) => x.type.startsWith('image/'))
    if (f) onChange(f)
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => picker.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          take(e.dataTransfer.files)
        }}
        aria-label="Choose a new cover"
        className={cn(
          'group relative block w-full rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
          over && 'ring-2 ring-ring',
        )}
      >
        {preview ? (
          <img
            src={preview}
            alt="The new cover"
            className="aspect-[2/3] w-full rounded-md object-cover shadow-md"
          />
        ) : value === 'remove' ? (
          <div className="flex aspect-[2/3] w-full items-center justify-center rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
            calibre makes a plain cover when there is none
          </div>
        ) : (
          <Cover
            library={library}
            book={book}
            width={192}
            full
            eager
            className="w-full shadow-md"
          />
        )}
        <span className="absolute inset-0 flex items-center justify-center rounded-md bg-black/40 text-sm font-medium text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <IconPhotoUp className="mr-1.5 size-4" />
          Change
        </span>
      </button>
      <input
        ref={picker}
        type="file"
        accept="image/*"
        hidden
        aria-label="Cover picture"
        onChange={(e) => {
          take(e.target.files)
          e.target.value = ''
        }}
      />
      <div className="flex flex-wrap gap-1">
        {value !== null ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onChange(null)}
          >
            Keep the old cover
          </Button>
        ) : (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            onClick={() => onChange('remove')}
          >
            <IconTrash />
            Remove cover
          </Button>
        )}
      </div>
    </div>
  )
}
