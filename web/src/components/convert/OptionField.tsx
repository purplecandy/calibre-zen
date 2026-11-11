// One conversion option, drawn for its kind: a checkbox, a box for text or a
// number, a list to choose from, and so on. calibre's help for the option is
// one tap away, as its tooltip is on the desktop.
import { useEffect, useId, useState } from 'react'
import { IconInfoCircle, IconPlus, IconX } from '@tabler/icons-react'
import {
  choicesFor,
  type ConversionData,
  type Field,
  type Group,
} from '@/lib/conversion'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  field: Exclude<Field, { kind: 'heading' }>
  group: Group
  data: ConversionData
  value: unknown
  disabled: boolean
  onChange: (value: unknown) => void
}

function Help({ label, text }: { label: string; text: string | undefined }) {
  if (!text) return null
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7 shrink-0 text-muted-foreground"
          aria-label={`About ${label}`}
        >
          <IconInfoCircle className="size-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 text-sm whitespace-pre-line">
        {text}
      </PopoverContent>
    </Popover>
  )
}

/** Text boxes give null when empty, as calibre's own fields do. */
function textValue(v: string): string | null {
  return v.trim() ? v : null
}

export function OptionField({
  field,
  group,
  data,
  value,
  disabled,
  onChange,
}: Props) {
  const id = useId()
  const help = data.conversion_options.help[field.name]
  const label = (
    <Label htmlFor={id} className={cn('font-normal', disabled && 'opacity-50')}>
      {field.label}
    </Label>
  )

  if (field.kind === 'check') {
    return (
      <div className="flex items-start gap-2.5 py-1">
        <Checkbox
          id={id}
          checked={!!value}
          disabled={disabled}
          onCheckedChange={(v) => onChange(v === true)}
          className="mt-0.5"
        />
        <div className="min-w-0 flex-1">{label}</div>
        <Help label={field.label} text={help} />
      </div>
    )
  }

  let control
  switch (field.kind) {
    case 'text':
      control = (
        <Input
          id={id}
          value={(value as string | null) ?? ''}
          disabled={disabled}
          onChange={(e) => onChange(textValue(e.target.value))}
          className={field.wide ? 'font-mono text-xs' : undefined}
        />
      )
      break
    case 'textarea':
      control = (
        <Textarea
          id={id}
          value={(value as string | null) ?? ''}
          disabled={disabled}
          onChange={(e) => onChange(textValue(e.target.value))}
          rows={6}
          className="font-mono text-xs"
        />
      )
      break
    case 'number':
      control = (
        <div className="flex items-center gap-2">
          <Input
            id={id}
            type="number"
            inputMode={field.int ? 'numeric' : 'decimal'}
            value={value === null || value === undefined ? '' : String(value)}
            min={field.min}
            max={field.max}
            step={field.step}
            disabled={disabled}
            onChange={(e) => {
              const n = field.int
                ? parseInt(e.target.value, 10)
                : parseFloat(e.target.value)
              onChange(Number.isNaN(n) ? null : n)
            }}
            className="w-32"
          />
          {field.unit && (
            <span className="text-sm text-muted-foreground">{field.unit}</span>
          )}
        </div>
      )
      break
    case 'choice': {
      const choices = choicesFor(field, group, data)
      const current = value === null || value === undefined ? '' : String(value)
      control = (
        <Select value={current} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger id={id} className="w-full sm:w-72">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="max-h-80">
            {choices.map(([v, text]) => (
              <SelectItem key={v} value={v}>
                {text}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )
      break
    }
    case 'subset': {
      const on = new Set(
        String(value ?? '')
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      )
      const choices = choicesFor(field, group, data)
      control = (
        <div className="grid gap-2 sm:grid-cols-2" id={id}>
          {choices.map(([v, text]) => (
            <Label key={v} className="items-start font-normal">
              <Checkbox
                checked={on.has(v)}
                disabled={disabled}
                onCheckedChange={(c) => {
                  const next = new Set(on)
                  if (c === true) next.add(v)
                  else next.delete(v)
                  onChange(
                    choices
                      .map(([k]) => k)
                      .filter((k) => next.has(k))
                      .join(','),
                  )
                }}
                className="mt-0.5"
              />
              {text}
            </Label>
          ))}
        </div>
      )
      break
    }
    case 'searchReplace':
      return (
        <SearchReplace value={value} disabled={disabled} onChange={onChange} />
      )
  }

  return (
    <div className="grid gap-1.5 py-1">
      <div className="flex items-center gap-1">
        <div className="min-w-0 flex-1">{label}</div>
        <Help label={field.label} text={help} />
      </div>
      {control}
    </div>
  )
}

/** calibre keeps the pairs as JSON text: [["search", "replace"], ...]. */
function parsePairs(value: unknown): [string, string][] {
  try {
    const parsed: unknown = JSON.parse(String(value ?? '[]'))
    if (Array.isArray(parsed))
      return parsed.map((p) => [String(p?.[0] ?? ''), String(p?.[1] ?? '')])
  } catch {
    // an empty list
  }
  return []
}

function SearchReplace({
  value,
  disabled,
  onChange,
}: {
  value: unknown
  disabled: boolean
  onChange: (value: unknown) => void
}) {
  // The rows on screen, with an empty one to type into. Only rows with a
  // search are sent.
  const [rows, setRows] = useState<[string, string][]>(() => [
    ...parsePairs(value),
    ['', ''],
  ])
  const saved = JSON.stringify(rows.filter(([s]) => s))
  useEffect(() => {
    // Restore defaults changes the value from outside.
    if (JSON.stringify(parsePairs(value)) !== saved)
      setRows([...parsePairs(value), ['', '']])
  }, [value])
  const save = (next: [string, string][]) => {
    setRows(next)
    onChange(JSON.stringify(next.filter(([s]) => s)))
  }
  const edit = (i: number, j: 0 | 1, text: string) =>
    save(
      rows.map((p, k) =>
        k === i ? (j === 0 ? [text, p[1]] : [p[0], text]) : p,
      ),
    )
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        Each search is a regular expression. What it finds is replaced in the
        book before it is converted.
      </p>
      {rows.map(([s, r], i) => (
        <div key={i} className="flex items-end gap-2">
          <div className="grid min-w-0 flex-1 gap-1.5">
            <span className="text-xs text-muted-foreground">Search</span>
            <Input
              value={s}
              disabled={disabled}
              className="font-mono text-xs"
              aria-label={`Search ${i + 1}`}
              onChange={(e) => edit(i, 0, e.target.value)}
            />
          </div>
          <div className="grid min-w-0 flex-1 gap-1.5">
            <span className="text-xs text-muted-foreground">Replace</span>
            <Input
              value={r}
              disabled={disabled}
              className="font-mono text-xs"
              aria-label={`Replace ${i + 1}`}
              onChange={(e) => edit(i, 1, e.target.value)}
            />
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Remove search ${i + 1}`}
            disabled={disabled || rows.length < 2}
            onClick={() => save(rows.filter((_, k) => k !== i))}
          >
            <IconX className="size-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="justify-self-start"
        disabled={disabled || !rows[rows.length - 1]?.[0]}
        onClick={() => setRows([...rows, ['', '']])}
      >
        <IconPlus />
        Add another
      </Button>
    </div>
  )
}
