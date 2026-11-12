// What to type, before the first search.
export function Help() {
  return (
    <div className="grid gap-2 text-sm text-muted-foreground">
      <p>
        Type a few words to find the books that contain them. Put a phrase in
        quotes to find those words together.
      </p>
      <p>
        Use <code>AND</code>, <code>OR</code> and <code>NOT</code> to combine
        words, and <code>*</code> at the end of a word to match its start, as in{' '}
        <code>light*</code>.
      </p>
    </div>
  )
}
