// One editor per kind of field (model.ts): what a person sees for a title,
// a list of tags, a series and its number, a date, a rating, a yes or no.
import { lazy, Suspense, useMemo, useRef, useState } from 'react'
import {
  IconPlus,
  IconStar,
  IconStarFilled,
  IconStarHalfFilled,
  IconX,
} from '@tabler/icons-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { FieldSpec, FormValue, SeriesValue } from './model'
import { Suggest } from './Suggest'

const RichText = lazy(() => import('./RichText'))

interface EditorProps<T extends FormValue> {
  spec: FieldSpec
  library: string
  id: string
  value: T
  onChange: (v: T) => void
}

/** A list of names as chips, typed one at a time. */
function Names({ spec, library, id, value, onChange }: EditorProps<string[]>) {
  const [text, setText] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const sep = spec.separator ?? ','
  const skip = useMemo(() => new Set(value), [value])

  const add = (raw: string) => {
    const parts = raw
      .split(sep)
      .map((x) => x.trim())
      .filter((x) => x && !value.includes(x))
    if (parts.length) onChange([...value, ...new Set(parts)])
    setText('')
  }

  return (
    <div
      className="flex min-h-9 flex-wrap items-center gap-1 rounded-md border border-input px-1.5 py-1 shadow-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 dark:bg-input/30"
      onClick={(e) => e.target === e.currentTarget && input.current?.focus()}
    >
      {value.map((v) => (
        <span
          key={v}
          className="inline-flex max-w-full items-center gap-0.5 rounded-md bg-secondary py-0.5 pr-0.5 pl-2 text-xs text-secondary-foreground"
        >
          <span className="truncate">{v}</span>
          <button
            type="button"
            className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label={`Remove ${v}`}
            onClick={() => onChange(value.filter((x) => x !== v))}
          >
            <IconX className="size-3" />
          </button>
        </span>
      ))}
      <Suggest
        ref={input}
        id={id}
        library={library}
        field={spec.field}
        value={text}
        skip={skip}
        onChange={(t) => (t.includes(sep) ? add(t) : setText(t))}
        onPick={add}
        onBlur={() => text.trim() && add(text)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            if (text.trim()) add(text)
          } else if (e.key === 'Backspace' && !text && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        placeholder={value.length ? '' : `Add ${spec.name.toLowerCase()}`}
        className="min-w-32 flex-1"
        // The box around it draws the border.
        style={{ border: 0, boxShadow: 'none', background: 'transparent' }}
      />
    </div>
  )
}

function Series({
  spec,
  library,
  id,
  value,
  onChange,
}: EditorProps<SeriesValue>) {
  return (
    <div className="flex gap-2">
      <Suggest
        id={id}
        library={library}
        field={spec.field}
        value={value.name}
        onChange={(name) => onChange({ ...value, name })}
        className="flex-1"
      />
      <Input
        type="number"
        step="any"
        min={0}
        inputMode="decimal"
        value={value.index}
        onChange={(e) => onChange({ ...value, index: e.target.value })}
        aria-label={`Number in ${spec.name.toLowerCase()}`}
        className="w-20"
      />
    </div>
  )
}

/** Five stars, in halves where the column allows them. */
function Rating({ spec, id, value, onChange }: EditorProps<number>) {
  const step = spec.halfStars ? 1 : 2
  const stars = value / 2
  const label = (n: number) =>
    n ? `${n / 2} ${n === 2 ? 'star' : 'stars'}` : 'No rating'
  return (
    <div className="flex items-center gap-2">
      <div
        id={id}
        role="slider"
        tabIndex={0}
        aria-valuemin={0}
        aria-valuemax={10}
        aria-valuenow={value}
        aria-valuetext={label(value)}
        aria-label={spec.name}
        className="flex rounded-md py-1 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        onKeyDown={(e) => {
          const d =
            e.key === 'ArrowRight' || e.key === 'ArrowUp'
              ? step
              : e.key === 'ArrowLeft' || e.key === 'ArrowDown'
                ? -step
                : 0
          if (d) {
            e.preventDefault()
            onChange(Math.min(10, Math.max(0, value + d)))
          }
        }}
      >
        {[1, 2, 3, 4, 5].map((i) => {
          const Icon =
            stars >= i
              ? IconStarFilled
              : stars >= i - 0.5
                ? IconStarHalfFilled
                : IconStar
          return (
            <button
              key={i}
              type="button"
              tabIndex={-1}
              aria-hidden
              className="p-0.5 text-foreground"
              onClick={(e) => {
                const r = e.currentTarget.getBoundingClientRect()
                const half = spec.halfStars && e.clientX < r.left + r.width / 2
                const n = i * 2 - (half ? 1 : 0)
                onChange(n === value ? 0 : n)
              }}
            >
              <Icon className={cn('size-5', stars < i - 0.5 && 'opacity-30')} />
            </button>
          )
        })}
      </div>
      {value > 0 && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() => onChange(0)}
        >
          Clear
        </Button>
      )}
    </div>
  )
}

const NONE = '\u0000none'

function Choice({
  id,
  value,
  onChange,
  options,
}: EditorProps<string> & { options: [string, string][] }) {
  return (
    <Select
      value={value || NONE}
      onValueChange={(v) => onChange(v === NONE ? '' : v)}
    >
      <SelectTrigger id={id} className="w-full sm:w-60">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>
          <span className="text-muted-foreground">Not set</span>
        </SelectItem>
        {options.map(([v, label]) => (
          <SelectItem key={v} value={v}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function Identifiers({ id, value, onChange }: EditorProps<[string, string][]>) {
  const set = (i: number, part: 0 | 1, text: string) =>
    onChange(
      value.map((row, j) =>
        j === i ? (part ? [row[0], text] : [text, row[1]]) : row,
      ),
    )
  return (
    <div className="flex flex-col gap-2">
      {value.map(([k, v], i) => (
        <div key={i} className="flex gap-2">
          <Input
            id={i === 0 ? id : undefined}
            value={k}
            onChange={(e) => set(i, 0, e.target.value)}
            placeholder="isbn"
            aria-label="Kind"
            className="w-28"
          />
          <Input
            value={v}
            onChange={(e) => set(i, 1, e.target.value)}
            aria-label={`${k || 'Identifier'} value`}
            className="flex-1"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Remove ${k || 'this identifier'}`}
            onClick={() => onChange(value.filter((_, j) => j !== i))}
          >
            <IconX />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        id={value.length ? undefined : id}
        onClick={() => onChange([...value, ['', '']])}
      >
        <IconPlus />
        Add an identifier
      </Button>
    </div>
  )
}

/** The editor for one field, by its kind. */
export function FieldEditor({
  spec,
  library,
  id,
  value,
  initial,
  onChange,
}: {
  spec: FieldSpec
  library: string
  id: string
  value: FormValue
  initial: FormValue
  onChange: (v: FormValue) => void
}) {
  const p = { spec, library, id }
  switch (spec.kind) {
    case 'names':
      return <Names {...p} value={value as string[]} onChange={onChange} />
    case 'series':
      return <Series {...p} value={value as SeriesValue} onChange={onChange} />
    case 'rating':
      return <Rating {...p} value={value as number} onChange={onChange} />
    case 'identifiers':
      return (
        <Identifiers
          {...p}
          value={value as [string, string][]}
          onChange={onChange}
        />
      )
    case 'enum':
      return (
        <Choice
          {...p}
          value={value as string}
          onChange={onChange}
          options={(spec.values ?? []).map((v) => [v, v])}
        />
      )
    case 'bool':
      return (
        <Choice
          {...p}
          value={value as string}
          onChange={onChange}
          options={[
            ['yes', 'Yes'],
            ['no', 'No'],
          ]}
        />
      )
    case 'date':
      return (
        <div className="flex items-center gap-2">
          <Input
            id={id}
            type="date"
            min="0101-01-02"
            value={value as string}
            onChange={(e) => onChange(e.target.value)}
            className="w-44"
          />
          {value !== '' && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              onClick={() => onChange('')}
            >
              Clear
            </Button>
          )}
        </div>
      )
    case 'number':
      return (
        <Input
          id={id}
          type="number"
          step={spec.integer ? 1 : 'any'}
          inputMode={spec.integer ? 'numeric' : 'decimal'}
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          className="w-36"
        />
      )
    case 'long-text':
    case 'markdown':
      return (
        <Textarea
          id={id}
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          className="min-h-32"
        />
      )
    case 'html':
      return (
        <Suspense fallback={<div className="h-48 rounded-md border" />}>
          <RichText
            initial={initial as string}
            label={spec.name}
            onChange={(html) => onChange(html)}
          />
        </Suspense>
      )
  }
  if (spec.suggest) {
    return (
      <Suggest
        id={id}
        library={library}
        field={spec.field}
        value={value as string}
        onChange={onChange}
      />
    )
  }
  return (
    <Input
      id={id}
      value={value as string}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}
