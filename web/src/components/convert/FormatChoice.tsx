// From or To: one of the formats calibre offers for this book.
import { Field } from '@/components/app/Field'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export function FormatChoice({
  label,
  value,
  formats,
  disabled,
  onChange,
}: {
  label: string
  value: string
  formats: string[]
  disabled: boolean
  onChange: (f: string) => void
}) {
  const id = `format-${label.toLowerCase()}`
  return (
    <Field label={label} id={id}>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="max-h-80">
          {formats.map((f) => (
            <SelectItem key={f} value={f}>
              {f}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  )
}
