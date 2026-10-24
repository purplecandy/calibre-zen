// The editor for a book's comments, comments columns and notes: formatted
// text, with the HTML itself one click away. TipTap, loaded only when an
// editor is first shown (see LazyRichText in fields.tsx).
//
// TipTap keeps the parts of HTML it has a rule for. Paragraphs, headings,
// bold, italic, underline, links, lists, quotes and pictures survive; a
// table or a coloured span does not. So nothing is sent unless the text was
// changed, and the HTML view edits anything as it is.
import { useRef, useState } from 'react'
import { EditorContent, useEditor, useEditorState } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import {
  IconArrowBackUp,
  IconArrowForwardUp,
  IconBlockquote,
  IconBold,
  IconCode,
  IconH3,
  IconItalic,
  IconLink,
  IconList,
  IconListNumbers,
  IconPhoto,
  IconStrikethrough,
  IconUnderline,
} from '@tabler/icons-react'
import { readAsDataUrl } from '@/lib/edit'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Toggle } from '@/components/ui/toggle'
import './rich-text.css'

export interface RichTextProps {
  /** The HTML it starts with. Later changes to it are not followed. */
  initial: string
  onChange: (html: string, text: string) => void
  /** Pictures can be added, as in notes. */
  images?: boolean
  label: string
  className?: string
}

export default function RichText({
  initial,
  onChange,
  images,
  label,
  className,
}: RichTextProps) {
  const [source, setSource] = useState<string | null>(null)
  const [linking, setLinking] = useState<string | null>(null)
  const picker = useRef<HTMLInputElement>(null)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        codeBlock: false,
        link: { openOnClick: false, autolink: true },
      }),
      ...(images ? [Image.configure({ allowBase64: true })] : []),
    ],
    content: initial,
    editorProps: {
      attributes: {
        class: 'zen-prose zen-rich-text min-h-40 px-3 py-2 text-sm',
        'aria-label': label,
        'aria-multiline': 'true',
        role: 'textbox',
      },
    },
    onUpdate: ({ editor }) => onChange(editor.getHTML(), editor.getText()),
  })

  const active = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      bold: e?.isActive('bold') ?? false,
      italic: e?.isActive('italic') ?? false,
      underline: e?.isActive('underline') ?? false,
      strike: e?.isActive('strike') ?? false,
      heading: e?.isActive('heading', { level: 3 }) ?? false,
      bullet: e?.isActive('bulletList') ?? false,
      ordered: e?.isActive('orderedList') ?? false,
      quote: e?.isActive('blockquote') ?? false,
      link: e?.isActive('link') ?? false,
      undo: e?.can().undo() ?? false,
      redo: e?.can().redo() ?? false,
    }),
  })

  if (!editor || !active) {
    return <div className={cn('h-48 rounded-md border', className)} />
  }

  const chain = () => editor.chain().focus()
  const mark = (
    on: boolean,
    name: string,
    Icon: typeof IconBold,
    run: () => void,
  ) => (
    <Toggle
      size="sm"
      pressed={on}
      onPressedChange={run}
      aria-label={name}
      title={name}
      disabled={source !== null}
    >
      <Icon />
    </Toggle>
  )

  const showSource = () => {
    if (source === null) {
      setSource(editor.getHTML())
    } else {
      editor.commands.setContent(source, { emitUpdate: false })
      setSource(null)
    }
  }

  const addPicture = async (file: File | undefined) => {
    if (!file) return
    const src = await readAsDataUrl(file)
    chain().setImage({ src, alt: file.name }).run()
  }

  return (
    <div
      className={cn(
        'overflow-hidden rounded-md border border-input shadow-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 dark:bg-input/30',
        className,
      )}
    >
      <div
        role="toolbar"
        aria-label={`Formatting for ${label}`}
        className="flex flex-wrap items-center gap-0.5 border-b bg-muted/40 p-1"
      >
        {mark(active.bold, 'Bold', IconBold, () => chain().toggleBold().run())}
        {mark(active.italic, 'Italic', IconItalic, () =>
          chain().toggleItalic().run(),
        )}
        {mark(active.underline, 'Underline', IconUnderline, () =>
          chain().toggleUnderline().run(),
        )}
        {mark(active.strike, 'Strikethrough', IconStrikethrough, () =>
          chain().toggleStrike().run(),
        )}
        {mark(active.heading, 'Heading', IconH3, () =>
          chain().toggleHeading({ level: 3 }).run(),
        )}
        {mark(active.bullet, 'Bulleted list', IconList, () =>
          chain().toggleBulletList().run(),
        )}
        {mark(active.ordered, 'Numbered list', IconListNumbers, () =>
          chain().toggleOrderedList().run(),
        )}
        {mark(active.quote, 'Quote', IconBlockquote, () =>
          chain().toggleBlockquote().run(),
        )}
        {mark(active.link, 'Link', IconLink, () =>
          setLinking(
            linking === null
              ? ((editor.getAttributes('link').href as string) ?? '')
              : null,
          ),
        )}
        {images && (
          <>
            {mark(false, 'Add a picture', IconPhoto, () =>
              picker.current?.click(),
            )}
            <input
              ref={picker}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                void addPicture(e.target.files?.[0])
                e.target.value = ''
              }}
            />
          </>
        )}
        <span className="mx-1 h-5 w-px bg-border" aria-hidden />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Undo"
          title="Undo"
          disabled={!active.undo || source !== null}
          onClick={() => chain().undo().run()}
        >
          <IconArrowBackUp />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Redo"
          title="Redo"
          disabled={!active.redo || source !== null}
          onClick={() => chain().redo().run()}
        >
          <IconArrowForwardUp />
        </Button>
        <Toggle
          size="sm"
          className="ml-auto px-2 text-xs"
          pressed={source !== null}
          onPressedChange={showSource}
          aria-label="Edit as HTML"
          title="Edit as HTML"
        >
          <IconCode />
          HTML
        </Toggle>
      </div>
      {linking !== null && source === null && (
        <form
          className="flex items-center gap-2 border-b p-2"
          onSubmit={(e) => {
            e.preventDefault()
            const href = linking.trim()
            if (href) {
              chain().extendMarkRange('link').setLink({ href }).run()
            } else {
              chain().extendMarkRange('link').unsetLink().run()
            }
            setLinking(null)
          }}
        >
          <Input
            autoFocus
            type="url"
            value={linking}
            onChange={(e) => setLinking(e.target.value)}
            placeholder="https://"
            aria-label="Link address"
            className="h-8"
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.stopPropagation()
                setLinking(null)
              }
            }}
          />
          <Button type="submit" size="sm">
            {linking.trim() ? 'Set link' : 'Remove link'}
          </Button>
        </form>
      )}
      {source !== null ? (
        <Textarea
          value={source}
          onChange={(e) => {
            setSource(e.target.value)
            const doc = new DOMParser().parseFromString(
              e.target.value,
              'text/html',
            )
            onChange(e.target.value, doc.body.textContent ?? '')
          }}
          aria-label={`${label}, as HTML`}
          spellCheck={false}
          className="min-h-40 rounded-none border-0 font-mono text-xs shadow-none focus-visible:ring-0"
        />
      ) : (
        <EditorContent editor={editor} />
      )}
    </div>
  )
}
