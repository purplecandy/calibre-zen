// The cover in the editor: the one the book has, a new picture chosen or
// dropped on it, or none. Nothing is sent until the form is saved.
import { useEffect, useState } from 'react'
import { IconPhotoUp, IconTrash } from '@tabler/icons-react'
import type { Book } from '@/lib/api'
import type { CoverChange } from '@/lib/model/edit'
import { FilePicker } from '@/components/app/FilePicker'
import { Button } from '@/components/ui/button'
import { Cover } from '@/components/library/Cover'

export function CoverField({
  book,
  value,
  onChange,
}: {
  book: Book & { id: number }
  value: CoverChange
  onChange: (c: CoverChange) => void
}) {
  const [preview, setPreview] = useState<string | null>(null)

  useEffect(() => {
    if (!(value instanceof File)) return setPreview(null)
    const url = URL.createObjectURL(value)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [value])

  return (
    <div className="flex flex-col gap-2">
      <FilePicker
        label="Cover picture"
        accept="image/*"
        drop
        onPick={([file]) => onChange(file)}
      >
        <button
          type="button"
          aria-label="Choose a new cover"
          className="group relative block w-full rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[over]:ring-2 data-[over]:ring-ring"
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
      </FilePicker>
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
