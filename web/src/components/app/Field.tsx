// A labelled control, and a set of choices. Every form in the app lays its
// rows out with these, so a label, its control and its hint line up the same
// way everywhere:
//
//   <Field label="New password" id="pw-new">
//     <Input id="pw-new" type="password" … />
//   </Field>
//
//   <Choices legend="Library" name="copy-to" value={target}
//     onChange={setTarget} options={libraries} />
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

/** A label over its control, with an optional hint and error under it. */
export function Field({
  label,
  id,
  hint,
  error,
  className,
  children,
}: {
  label: ReactNode
  /** The control's id, so the label points at it. */
  id: string
  hint?: ReactNode
  error?: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={cn('grid gap-2', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

/** One of a few choices, as radio buttons under a heading. */
export function Choices<T extends string>({
  legend,
  name,
  value,
  onChange,
  options,
  look = 'plain',
  className,
}: {
  legend?: ReactNode
  /** Makes each button's id unique on the page. */
  name: string
  value: T
  onChange: (value: T) => void
  options: readonly (readonly [T, ReactNode])[]
  /** Plain rows, or bordered cards for a setting with few choices. */
  look?: 'plain' | 'cards'
  className?: string
}) {
  const group = (
    <RadioGroup
      value={value}
      onValueChange={(v) => onChange(v as T)}
      className={className}
    >
      {options.map(([v, text]) => (
        <Label
          key={v}
          htmlFor={`${name}-${v}`}
          className={cn(
            'flex items-center gap-2 font-normal',
            look === 'cards' &&
              'cursor-pointer gap-2.5 rounded-md border px-3 py-2.5 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-accent',
          )}
        >
          <RadioGroupItem id={`${name}-${v}`} value={v} />
          {text}
        </Label>
      ))}
    </RadioGroup>
  )
  if (!legend) return group
  return (
    <fieldset className="flex flex-col gap-2">
      {/* Cards sit under a section's own heading, so their legend is quieter. */}
      <legend
        className={cn(
          'mb-2 text-sm',
          look === 'cards' ? 'text-muted-foreground' : 'font-medium',
        )}
      >
        {legend}
      </legend>
      {group}
    </fieldset>
  )
}
