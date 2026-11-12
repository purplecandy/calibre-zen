// Converting a book: the options calibre offers, grouped the way its web app
// and the desktop group them (the groups are in conversion-groups.ts), and
// where a conversion that was started has got to.
import { isDeepEqual, pick } from 'remeda'
import type {
  ConversionData,
  ConversionOptions,
  JobStatus,
} from '@/lib/conversion'
import { COMMON_GROUPS, FORMAT_GROUPS } from './conversion-groups'

// The options {{{

export type Field =
  | { kind: 'check'; name: string; label: string }
  | { kind: 'text'; name: string; label: string; wide?: boolean }
  | { kind: 'textarea'; name: string; label: string }
  | {
      kind: 'number'
      name: string
      label: string
      int?: boolean
      min?: number
      max?: number
      step?: number
      unit?: string
    }
  | {
      kind: 'choice'
      name: string
      label: string
      /** Fixed choices, or the key of the plugin's ui_data that has them, or a profile list. */
      choices:
        | string[]
        | Record<string, string>
        | { uiData: string }
        | { profiles: 'input' | 'output' }
    }
  | { kind: 'subset'; name: string; label: string; choices: { uiData: string } }
  | { kind: 'searchReplace'; name: string; label: string }
  | { kind: 'heading'; label: string }

/**
 * A field that is off unless another is on (`when: true`) or off
 * (`when: false`), as calibre's listeners in conversion_widgets.pyj do.
 */
export interface Dependency {
  on: string
  when: boolean
}

export interface Group {
  id: string
  title: string
  /** For input_fmt and output_fmt: the plugin's commit_name it applies to. */
  plugin?: string
  fields: Field[]
  /** Fields turned off by another field's value. */
  depends?: Record<string, Dependency>
}

/** The groups for one conversion, in calibre's order: input, the common ones, output. */
export function groupsFor(
  c: ConversionOptions,
  input: string,
  output: string,
): Group[] {
  const groups: Group[] = []
  const inp = FORMAT_GROUPS[c.input_plugin_name]
  if (inp)
    groups.push({
      id: 'input',
      title: `${input} input`,
      plugin: c.input_plugin_name,
      ...inp,
    })
  groups.push(...COMMON_GROUPS)
  const out = FORMAT_GROUPS[c.output_plugin_name]
  if (out)
    groups.push({
      id: 'output',
      title: `${output} output`,
      plugin: c.output_plugin_name,
      ...out,
    })
  return groups
}

/** Choices for a choice field: value to label, in order. */
export function choicesFor(
  field: Extract<Field, { kind: 'choice' | 'subset' }>,
  group: Group,
  data: ConversionData,
): [string, string][] {
  const c = field.choices
  if (Array.isArray(c)) return c.map((v) => [v, v])
  if ('profiles' in c && (c.profiles === 'input' || c.profiles === 'output'))
    return Object.entries(data.profiles[c.profiles]).map(([k, p]) => [
      k,
      p.name,
    ])
  if ('uiData' in c && typeof c.uiData === 'string') {
    const ui =
      group.id === 'output'
        ? data.conversion_options.output_ui_data
        : data.conversion_options.input_ui_data
    const v = ui?.[c.uiData]
    if (Array.isArray(v)) return v.map((x) => [String(x), String(x)])
    if (v && typeof v === 'object')
      return Object.entries(v as Record<string, unknown>).map(([k, l]) => [
        k,
        String(l),
      ])
    return []
  }
  return Object.entries(c as Record<string, string>)
}

/** The names a group sets, for its Restore defaults. */
export function namesIn(group: Group): string[] {
  return group.fields.flatMap((f) => ('name' in f ? [f.name] : []))
}

/**
 * The options to send: the ones the book starts with, and what was changed
 * here over them. A change to an option this pair of formats lacks is left
 * out, so it is kept for a format that has it.
 */
export function optionValues(
  opts: ConversionOptions,
  changes: Record<string, unknown>,
): Record<string, unknown> {
  return { ...opts.options, ...pick(changes, Object.keys(opts.options)) }
}

/** Whether a field is off: the server says so, or another field turns it off. */
export function isOff(
  opts: ConversionOptions,
  group: Group,
  values: Record<string, unknown>,
  name: string,
): boolean {
  if (opts.disabled.includes(name)) return true
  const dep = group.depends?.[name]
  return !!dep && !!values[dep.on] !== dep.when
}

/** A group's options at the library's defaults, for its Restore defaults. */
export function defaultsOf(
  group: Group,
  opts: ConversionOptions,
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const n of namesIn(group))
    if (n in opts.defaults) out[n] = opts.defaults[n]
  return out
}

/** Text boxes give null when empty, as calibre's own fields do. */
export function textOption(v: string): string | null {
  return v.trim() ? v : null
}

/** Search and replace: calibre keeps the pairs as JSON text, [["search", "replace"], ...]. */
export function readRules(value: unknown): [string, string][] {
  try {
    const parsed: unknown = JSON.parse(String(value ?? '[]'))
    if (Array.isArray(parsed))
      return parsed.map((p) => [String(p?.[0] ?? ''), String(p?.[1] ?? '')])
  } catch {
    // an empty list
  }
  return []
}

/** The pairs with a search, as calibre keeps them. */
export function writeRules(rows: [string, string][]): string {
  return JSON.stringify(rows.filter(([s]) => s))
}

/** Whether two lists of pairs are the same. */
export function sameRules(
  a: [string, string][],
  b: [string, string][],
): boolean {
  return isDeepEqual(a, b)
}

// }}}

// Jobs {{{

/** Where a conversion is, as the page shows it. */
export type Job =
  | { state: 'idle' }
  | { state: 'running'; percent: number; msg: string }
  | { state: 'done'; fmt: string; size: number }
  | { state: 'failed'; log: string; aborted: boolean }
  | { state: 'error'; message: string }

/** Where a followed job is, from its last answer. */
export function jobState(s: JobStatus | undefined): Job {
  if (!s) return { state: 'running', percent: 0, msg: '' }
  if (s.running) return { state: 'running', percent: s.percent, msg: s.msg }
  if (s.ok && s.fmt)
    return { state: 'done', fmt: s.fmt.toUpperCase(), size: s.size ?? 0 }
  return {
    state: 'failed',
    log: [s.traceback, s.log].filter(Boolean).join('\n\n'),
    aborted: s.was_aborted,
  }
}

// }}}
