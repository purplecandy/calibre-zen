// The search box, with its two choices: match related words, and search
// only the books that match a calibre search. It starts from the address
// and follows it when Back changes it.
import { useEffect, useState } from 'react'
import { IconSearch } from '@tabler/icons-react'
import { setSetting, useSetting } from '@/lib/prefs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

export function SearchForm({
  q,
  restrict: shownRestrict,
  onSearch,
}: {
  /** The search in the address. */
  q: string
  /** The search limiting which books, in the address. */
  restrict: string
  onSearch: (q: string, restrict: string) => void
}) {
  const related = useSetting('ftsRelated')
  const [text, setText] = useState(q)
  const [restrict, setRestrict] = useState(shownRestrict)
  const [showRestrict, setShowRestrict] = useState(!!shownRestrict)
  useEffect(() => {
    setText(q)
    setRestrict(shownRestrict)
  }, [q, shownRestrict])

  return (
    <form
      role="search"
      className="grid gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        onSearch(text.trim(), showRestrict ? restrict.trim() : '')
      }}
    >
      <div className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Words or a phrase from inside a book"
            aria-label="Search the text of the books"
            className="pl-8"
            enterKeyHint="search"
            autoFocus
          />
        </div>
        <Button type="submit" disabled={!text.trim()}>
          Search
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <Label className="font-normal">
          <Switch
            checked={related}
            onCheckedChange={(v) => setSetting('ftsRelated', v)}
          />
          Match related words
        </Label>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground"
          aria-expanded={showRestrict}
          onClick={() => setShowRestrict((s) => !s)}
        >
          {showRestrict ? 'Search all books' : 'Search only some books'}
        </button>
      </div>
      {showRestrict && (
        <Input
          value={restrict}
          onChange={(e) => setRestrict(e.target.value)}
          placeholder="Only books matching a search, such as tags:fiction"
          aria-label="Only in books matching"
        />
      )}
    </form>
  )
}
