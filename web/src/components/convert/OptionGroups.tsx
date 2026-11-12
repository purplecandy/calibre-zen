// calibre's options for this conversion, a group at a time, each with its
// Restore defaults.
import type { ConversionData } from '@/lib/conversion'
import { isOff, type Group } from '@/lib/model/conversion'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { OptionField } from './OptionField'

export function OptionGroups({
  groups,
  data,
  values,
  running,
  onChange,
  onRestore,
}: {
  groups: Group[]
  data: ConversionData
  values: Record<string, unknown>
  running: boolean
  onChange: (name: string, value: unknown) => void
  onRestore: (group: Group) => void
}) {
  const opts = data.conversion_options
  return (
    <section className="grid gap-2">
      <h3 className="text-sm font-medium">Options</h3>
      <p className="text-sm text-muted-foreground">
        These start from the settings this book was last converted with, or from
        the library&rsquo;s defaults.
      </p>
      <Accordion type="multiple" className="rounded-xl border px-4">
        {groups.map((group) => (
          <AccordionItem key={group.id} value={group.id}>
            <AccordionTrigger>{group.title}</AccordionTrigger>
            <AccordionContent className="grid gap-2">
              {group.fields.map((field, i) =>
                field.kind === 'heading' ? (
                  <h4
                    key={i}
                    className="mt-3 text-xs font-medium text-muted-foreground first:mt-0"
                  >
                    {field.label}
                  </h4>
                ) : field.name in values ? (
                  <OptionField
                    key={field.name}
                    field={field}
                    group={group}
                    data={data}
                    value={values[field.name]}
                    disabled={running || isOff(opts, group, values, field.name)}
                    onChange={(v) => onChange(field.name, v)}
                  />
                ) : null,
              )}
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 justify-self-start"
                disabled={running}
                onClick={() => onRestore(group)}
              >
                Restore defaults
              </Button>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  )
}
