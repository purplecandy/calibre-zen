// Converting a book: calibre's /conversion endpoints, and the options it
// offers grouped the way its web app and the desktop group them.
//
// The groups below follow src/pyj/book_list/conversion_widgets.pyj field by
// field, with calibre's own labels, so a setting is found under the same name
// as on the desktop. The server says which options exist for a pair of
// formats; a field it does not list is not shown.
import { qs, request, ServerError } from './api'

// The endpoints {{{

export interface ConversionOptions {
  options: Record<string, unknown>
  defaults: Record<string, unknown>
  disabled: string[]
  help: Record<string, string>
  input_plugin_name: string
  output_plugin_name: string
  input_ui_data: Record<string, unknown> | null
  output_ui_data: Record<string, unknown> | null
}

export interface Profile {
  name: string
  description: string
}

/** /conversion/book-data: what this book can be converted from and to. */
export interface ConversionData {
  input_formats: string[]
  output_formats: string[]
  profiles: { input: Record<string, Profile>; output: Record<string, Profile> }
  conversion_options: ConversionOptions
  title: string
  authors: string[]
  book_id: number
}

export function conversionData(
  library: string,
  id: number,
  input?: string,
  output?: string,
): Promise<ConversionData> {
  return request<ConversionData>(
    `conversion/book-data/${id}` +
      qs({
        library_id: library,
        input_fmt: input?.toLowerCase(),
        output_fmt: output?.toLowerCase(),
      }),
  )
}

/** Start a conversion. The answer is the job's number. */
export function startConversion(
  library: string,
  id: number,
  input: string,
  output: string,
  options: Record<string, unknown>,
): Promise<number> {
  return request<number>(
    `conversion/start/${id}` + qs({ library_id: library }),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_fmt: input,
        output_fmt: output,
        options,
        book_id: id,
      }),
    },
  )
}

export type JobStatus =
  | { running: true; percent: number; msg: string }
  | {
      running: false
      ok: boolean
      was_aborted: boolean
      traceback: string
      log: string
      size?: number
      fmt?: string
    }

/**
 * How a job is doing. The first answer after it ends is the last: the server
 * adds the new file to the book then, and forgets the job.
 */
export function jobStatus(
  library: string,
  job: number,
  abort = false,
): Promise<JobStatus> {
  return request<JobStatus>(
    `conversion/status/${job}` +
      qs({ library_id: library, abort_job: abort ? '1' : undefined }),
    { method: 'POST', body: '{}' },
  )
}

/** What to tell someone when the server says no. */
export function problem(e: unknown): string {
  if (e instanceof ServerError) {
    if (e.status === 403)
      return 'Your account can read this library but not change it.'
    if (e.status === 404) return 'This book is not in the library any more.'
    return e.message || `The server answered ${e.status}.`
  }
  return 'The server could not be reached.'
}

// }}}

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

const check = (name: string, label: string): Field => ({
  kind: 'check',
  name,
  label,
})
const text = (name: string, label: string, wide = false): Field => ({
  kind: 'text',
  name,
  label,
  wide,
})
const float = (
  name: string,
  label: string,
  o: Partial<Extract<Field, { kind: 'number' }>> = {},
): Field => ({
  kind: 'number',
  name,
  label,
  step: 0.1,
  min: 0,
  max: 100,
  ...o,
})
const int = (
  name: string,
  label: string,
  o: Partial<Extract<Field, { kind: 'number' }>> = {},
): Field => ({
  kind: 'number',
  name,
  label,
  int: true,
  step: 1,
  min: 0,
  max: 100,
  ...o,
})
const choice = (
  name: string,
  label: string,
  choices: Extract<Field, { kind: 'choice' }>['choices'],
): Field => ({
  kind: 'choice',
  name,
  label,
  choices,
})
const heading = (label: string): Field => ({ kind: 'heading', label })

/** Every field from `names` is off unless `on` is checked. */
function needs(
  on: string,
  names: string[],
  when = true,
): Record<string, Dependency> {
  return Object.fromEntries(names.map((n) => [n, { on, when }]))
}

const HEURISTICS = [
  'unwrap_lines',
  'html_unwrap_factor',
  'markup_chapter_headings',
  'renumber_headings',
  'delete_blank_paragraphs',
  'format_scene_breaks',
  'replace_scene_breaks',
  'dehyphenate',
  'italicize_common_cases',
  'fix_indents',
]

const COMIC = [
  'dont_grayscale',
  'dont_add_comic_pages_to_toc',
  'colors',
  'comic_image_size',
  'dont_normalize',
  'keep_aspect_ratio',
  'dont_sharpen',
  'disable_trim',
  'wide',
  'landscape',
  'right2left',
  'no_sort',
  'despeckle',
  'output_format',
]

const PDF_MARGINS = [
  'pdf_page_margin_left',
  'pdf_page_margin_top',
  'pdf_page_margin_right',
  'pdf_page_margin_bottom',
  'pdf_odd_even_offset',
]

/** The groups every conversion has, between the input's and the output's. */
export const COMMON_GROUPS: Group[] = [
  {
    id: 'look_and_feel',
    title: 'Look & feel',
    fields: [
      heading('Fonts'),
      check('disable_font_rescaling', 'Disable font size rescaling'),
      float('base_font_size', 'Base font size', { max: 50, unit: 'pt' }),
      text('font_size_mapping', 'Font size key'),
      float('minimum_line_height', 'Minimum line height', {
        max: 900,
        unit: '%',
      }),
      float('line_height', 'Line height', { unit: '%' }),
      text('embed_font_family', 'Embed font family'),
      check('embed_all_fonts', 'Embed all fonts in document'),
      check('subset_embedded_fonts', 'Subset all embedded fonts'),
      check('keep_ligatures', 'Keep ligatures'),
      heading('Text'),
      text('input_encoding', 'Input character encoding'),
      choice('change_justification', 'Text justification', {
        original: 'Original',
        left: 'Left align',
        justify: 'Justify text',
      }),
      check('smarten_punctuation', 'Smarten punctuation'),
      check('unsmarten_punctuation', 'Unsmarten punctuation'),
      check('asciiize', 'Transliterate Unicode characters to ASCII'),
      heading('Layout'),
      check('remove_paragraph_spacing', 'Remove spacing between paragraphs'),
      float('remove_paragraph_spacing_indent_size', 'Indent size', {
        min: -0.1,
        unit: 'em',
      }),
      check('insert_blank_line', 'Insert blank line between paragraphs'),
      float('insert_blank_line_size', 'Line size', { unit: 'em' }),
      check('linearize_tables', 'Linearize tables'),
      heading('Styling'),
      text('filter_css', 'Filter style information', true),
      { kind: 'textarea', name: 'extra_css', label: 'Extra CSS' },
    ],
    depends: {
      ...needs(
        'disable_font_rescaling',
        ['font_size_mapping', 'base_font_size'],
        false,
      ),
      ...needs('remove_paragraph_spacing', [
        'remove_paragraph_spacing_indent_size',
      ]),
    },
  },
  {
    id: 'page_setup',
    title: 'Page setup',
    fields: [
      float('margin_left', 'Left page margin', {
        unit: 'pt',
        min: -1,
        max: 200,
      }),
      float('margin_top', 'Top page margin', { unit: 'pt', min: -1, max: 200 }),
      float('margin_right', 'Right page margin', {
        unit: 'pt',
        min: -1,
        max: 200,
      }),
      float('margin_bottom', 'Bottom page margin', {
        unit: 'pt',
        min: -1,
        max: 200,
      }),
      choice('input_profile', 'Input profile', { profiles: 'input' }),
      choice('output_profile', 'Output profile', { profiles: 'output' }),
    ],
  },
  {
    id: 'search_and_replace',
    title: 'Search & replace',
    fields: [
      {
        kind: 'searchReplace',
        name: 'search_replace',
        label: 'Search & replace',
      },
    ],
  },
  {
    id: 'structure_detection',
    title: 'Structure detection',
    fields: [
      text('chapter', 'Detect chapters at', true),
      choice('chapter_mark', 'Chapter mark', [
        'pagebreak',
        'rule',
        'both',
        'none',
      ]),
      check('remove_first_image', 'Remove first image'),
      check('remove_fake_margins', 'Remove fake margins'),
      check('add_alt_text_to_img', 'Add alt text to images'),
      check('insert_metadata', 'Insert metadata at start of book'),
      text('page_breaks_before', 'Insert page breaks before', true),
      text('start_reading_at', 'Start reading at', true),
    ],
  },
  {
    id: 'toc',
    title: 'Table of Contents',
    fields: [
      check('use_auto_toc', 'Force use of auto-generated Table of Contents'),
      check(
        'no_chapters_in_toc',
        'Do not add detected chapters to the Table of Contents',
      ),
      check(
        'duplicate_links_in_toc',
        'Allow duplicate links when creating the Table of Contents',
      ),
      int('max_toc_links', 'Number of links to add to Table of Contents'),
      int('toc_threshold', 'Chapter threshold'),
      text('toc_filter', 'TOC filter'),
      text('level1_toc', 'Level 1 TOC (XPath expression)', true),
      text('level2_toc', 'Level 2 TOC (XPath expression)', true),
      text('level3_toc', 'Level 3 TOC (XPath expression)', true),
    ],
  },
  {
    id: 'heuristics',
    title: 'Heuristic processing',
    fields: [
      check('enable_heuristics', 'Enable heuristic processing'),
      check('unwrap_lines', 'Unwrap lines'),
      float('html_unwrap_factor', 'Line un-wrap factor', {
        max: 1,
        step: 0.05,
      }),
      check(
        'markup_chapter_headings',
        'Detect and markup unformatted chapter headings and sub headings',
      ),
      check(
        'renumber_headings',
        'Renumber sequences of <h1> or <h2> tags to prevent splitting',
      ),
      check('delete_blank_paragraphs', 'Delete blank lines between paragraphs'),
      check(
        'format_scene_breaks',
        'Ensure scene breaks are consistently formatted',
      ),
      text('replace_scene_breaks', 'Replace soft scene breaks'),
      check('dehyphenate', 'Remove unnecessary hyphens'),
      check('italicize_common_cases', 'Italicize common words and patterns'),
      check('fix_indents', 'Replace entity indents with CSS indents'),
    ],
    depends: needs('enable_heuristics', HEURISTICS),
  },
]

const TXT_OUTPUT: Field[] = [
  text('txt_output_encoding', 'Output encoding'),
  choice('newline', 'Line ending style', { uiData: 'newline_types' }),
  choice('txt_output_formatting', 'Formatting', { uiData: 'formatting_types' }),
  heading('Options for plain text output'),
  check('inline_toc', 'Inline TOC'),
  int('max_line_length', 'Maximum line length', { max: 1000 }),
  check('force_max_line_length', 'Force maximum line length'),
  heading('Options for Markdown and TexTile output'),
  check('keep_links', 'Do not remove links (<a> tags) before processing'),
  check(
    'keep_image_references',
    'Do not remove image references before processing',
  ),
  check(
    'use_alt_text_for_images',
    'Replace images with their alt attribute text',
  ),
  check('keep_color', 'Keep text color, when possible'),
]

/** Groups for one input or output format, by the plugin's commit_name. */
export const FORMAT_GROUPS: Record<string, Omit<Group, 'id' | 'title'>> = {
  comic_input: {
    fields: [
      check('no_process', 'Disable comic processing'),
      check(
        'dont_grayscale',
        'Disable conversion of images to black and white',
      ),
      check(
        'dont_add_comic_pages_to_toc',
        "Don't add links to pages to the Table of Contents for CBC files",
      ),
      int('colors', 'Number of colors', { max: 256, step: 8 }),
      text('comic_image_size', 'Override image size'),
      check('dont_normalize', 'Disable normalize'),
      check('keep_aspect_ratio', 'Keep aspect ratio'),
      check('dont_sharpen', 'Disable sharpening'),
      check('disable_trim', 'Disable trimming'),
      check('wide', 'Wide'),
      check('landscape', 'Landscape'),
      check('right2left', 'Right to left'),
      check('no_sort', "Don't sort"),
      check('despeckle', 'Despeckle'),
      choice('output_format', 'Output format', ['png', 'jpg']),
    ],
    depends: needs('no_process', COMIC, false),
  },
  fb2_input: {
    fields: [
      check(
        'no_inline_fb2_toc',
        'Do not insert a Table of Contents at the beginning of the book',
      ),
    ],
  },
  pdf_input: {
    fields: [
      float('unwrap_factor', 'Line un-wrapping factor', { max: 1, step: 0.01 }),
      check('no_images', 'No images'),
      choice('pdf_engine', 'PDF engine', {
        calibre: 'calibre',
        pdftohtml: 'pdftohtml',
      }),
      int('pdf_header_skip', 'Remove headers at top of page by', {
        min: -1,
        max: 999999,
      }),
      int('pdf_footer_skip', 'Remove footers at bottom of page by', {
        min: -1,
        max: 999999,
      }),
      text(
        'pdf_header_regex',
        'Regular expression to remove header at top of page',
        true,
      ),
      text(
        'pdf_footer_regex',
        'Regular expression to remove footer at bottom of page',
        true,
      ),
    ],
  },
  rtf_input: {
    fields: [check('ignore_wmf', 'Ignore WMF images in the RTF file')],
  },
  docx_input: {
    fields: [
      check(
        'docx_no_cover',
        'Do not try to autodetect a cover from images in the document',
      ),
      check(
        'docx_no_pagebreaks_between_notes',
        'Do not add a page after every endnote',
      ),
      check(
        'docx_inline_subsup',
        'Render superscripts and subscripts so that they do not affect the line height',
      ),
    ],
  },
  txt_input: {
    fields: [
      choice('paragraph_type', 'Paragraph style', {
        uiData: 'paragraph_types',
      }),
      choice('formatting_type', 'Formatting style', {
        uiData: 'formatting_types',
      }),
      check('preserve_spaces', 'Preserve spaces'),
      check(
        'txt_in_remove_indents',
        'Remove indents at the beginning of lines',
      ),
      {
        kind: 'subset',
        name: 'markdown_extensions',
        label: 'Allowed Markdown extensions',
        choices: { uiData: 'md_extensions' },
      },
    ],
  },
  epub_output: {
    fields: [
      check('dont_split_on_page_breaks', 'Do not split on page breaks'),
      check('no_default_epub_cover', 'No default cover'),
      check('epub_flatten', 'Flatten EPUB file structure'),
      check('no_svg_cover', 'No SVG cover'),
      check('preserve_cover_aspect_ratio', 'Preserve cover aspect ratio'),
      check('epub_inline_toc', 'Insert inline Table of Contents'),
      check(
        'epub_toc_at_end',
        'Put inserted Table of Contents at the end of the book',
      ),
      text('toc_title', 'Title for inserted ToC'),
      int('flow_size', 'Split files larger than', {
        unit: 'KB',
        max: 1000000,
        step: 20,
      }),
      text('epub_max_image_size', 'Shrink images larger than'),
      choice('epub_version', 'EPUB version', { uiData: 'versions' }),
    ],
  },
  kepub_output: {
    fields: [
      check('dont_split_on_page_breaks', 'Do not split on page breaks'),
      int('flow_size', 'Split files larger than', {
        unit: 'KB',
        max: 1000000,
        step: 20,
      }),
      text('kepub_max_image_size', 'Shrink images larger than'),
      text(
        'kepub_prefer_justification',
        'Prefer improved text justification to proper highlighting',
      ),
      check(
        'kepub_affect_hyphenation',
        'Enable/disable hyphenation for this book',
      ),
      check('kepub_disable_hyphenation', 'Prevent all hyphenation'),
      int('kepub_hyphenation_min_chars', 'Hyphenation: minimum word length', {
        unit: 'characters',
      }),
      int(
        'kepub_hyphenation_min_chars_before',
        'Hyphenation: minimum characters before',
        { unit: 'characters' },
      ),
      int(
        'kepub_hyphenation_min_chars_after',
        'Hyphenation: minimum characters after',
        { unit: 'characters' },
      ),
      int('kepub_hyphenation_limit_lines', 'Hyphenation: limit lines', {
        unit: 'lines',
      }),
    ],
  },
  docx_output: {
    fields: [
      choice('docx_page_size', 'Paper size', { uiData: 'page_sizes' }),
      text('docx_custom_page_size', 'Custom size'),
      float('docx_page_margin_left', 'Page left margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('docx_page_margin_top', 'Page top margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('docx_page_margin_right', 'Page right margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('docx_page_margin_bottom', 'Page bottom margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      check(
        'docx_no_toc',
        'Do not insert the Table of Contents as a page at the start of the document',
      ),
      check(
        'docx_no_cover',
        'Do not insert cover as image at start of document',
      ),
      check(
        'preserve_cover_aspect_ratio',
        'Preserve the aspect ratio of the image inserted as cover',
      ),
    ],
  },
  fb2_output: {
    fields: [
      choice('sectionize', 'Sectionize', { uiData: 'sectionize' }),
      choice('fb2_genre', 'Genre', { uiData: 'genres' }),
    ],
  },
  lrf_output: {
    fields: [
      check('autorotation', 'Enable auto-rotation of wide images'),
      float('wordspace', 'Wordspace', { min: 1, max: 20, unit: 'pt' }),
      float('minimum_indent', 'Minimum para. indent', { unit: 'pt' }),
      check('render_tables_as_images', 'Render tables as images'),
      float(
        'text_size_multiplier_for_rendered_tables',
        'Text size multiplier for text in rendered tables',
        { step: 0.01 },
      ),
      check('header', 'Add header'),
      float('header_separation', 'Header separation', { unit: 'pt' }),
      text('header_format', 'Header format'),
      text('serif_family', 'Serif font family'),
      text('sans_family', 'Sans-serif font family'),
      text('mono_family', 'Monospace font family'),
    ],
  },
  mobi_output: {
    fields: [
      check('no_inline_toc', 'Do not add Table of Contents to book'),
      text('toc_title', 'Title for Table of Contents'),
      check(
        'mobi_toc_at_start',
        'Put generated Table of Contents at start of book instead of end',
      ),
      check('mobi_ignore_margins', 'Ignore margins'),
      check('prefer_author_sort', 'Use author sort for author'),
      check(
        'mobi_keep_original_images',
        'Do not convert all images to JPEG (may result in images not working in older viewers)',
      ),
      check('dont_compress', 'Disable compression of the file contents'),
      choice('mobi_file_type', 'MOBI file type', { uiData: 'file_types' }),
      text('personal_doc', 'Personal Doc tag'),
      check(
        'share_not_sync',
        'Enable sharing of book content via Facebook, etc. WARNING: Disables last read syncing',
      ),
    ],
  },
  azw3_output: {
    fields: [
      check('no_inline_toc', 'Do not add Table of Contents to book'),
      text('toc_title', 'Title for Table of Contents'),
      check(
        'mobi_toc_at_start',
        'Put generated Table of Contents at start of book instead of end',
      ),
      check('prefer_author_sort', 'Use author sort for author'),
      check('dont_compress', 'Disable compression of the file contents'),
      check(
        'share_not_sync',
        'Enable sharing of book content via Facebook, etc. WARNING: Disables last read syncing',
      ),
    ],
  },
  pdb_output: {
    fields: [
      choice('format', 'Format', { uiData: 'formats' }),
      text('pdb_output_encoding', 'Output encoding'),
      check('inline_toc', 'Inline TOC'),
    ],
  },
  pdf_output: {
    fields: [
      check('use_profile_size', 'Use the paper size set in output profile'),
      choice('paper_size', 'Paper size', { uiData: 'paper_sizes' }),
      text('custom_size', 'Custom size'),
      choice('unit', 'Custom size unit', { uiData: 'units' }),
      check('pdf_no_cover', 'Discard book cover'),
      check('preserve_cover_aspect_ratio', 'Preserve aspect ratio of cover'),
      check('pdf_page_numbers', 'Add page numbers to the bottom of every page'),
      check('pdf_hyphenate', 'Break long words at the end of lines'),
      check('pdf_add_toc', 'Add a printable Table of Contents at the end'),
      text('toc_title', 'Title for ToC'),
      text('pdf_serif_family', 'Serif family'),
      text('pdf_sans_family', 'Sans family'),
      text('pdf_mono_family', 'Monospace family'),
      choice('pdf_standard_font', 'Standard font', { uiData: 'font_types' }),
      int('pdf_default_font_size', 'Default font size', { unit: 'px' }),
      int('pdf_mono_font_size', 'Monospace font size', { unit: 'px' }),
      text('pdf_page_number_map', 'Page number map'),
      check(
        'pdf_use_document_margins',
        'Use page margins from the document being converted',
      ),
      float('pdf_page_margin_left', 'Left page margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('pdf_page_margin_top', 'Top page margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('pdf_page_margin_right', 'Right page margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('pdf_page_margin_bottom', 'Bottom page margin', {
        unit: 'pt',
        min: -100,
        max: 500,
      }),
      float('pdf_odd_even_offset', 'Odd/even offset', {
        unit: 'pt',
        min: -500,
        max: 500,
      }),
      text('pdf_header_template', 'Header template', true),
      text('pdf_footer_template', 'Footer template', true),
    ],
    depends: {
      ...needs(
        'use_profile_size',
        ['paper_size', 'custom_size', 'unit'],
        false,
      ),
      ...needs('pdf_use_document_margins', PDF_MARGINS, false),
    },
  },
  pml_output: {
    fields: [
      text('pml_output_encoding', 'Output encoding'),
      check('inline_toc', 'Inline TOC'),
      check('full_image_depth', 'Do not reduce image size and depth'),
    ],
  },
  rb_output: { fields: [check('inline_toc', 'Inline TOC')] },
  txt_output: { fields: TXT_OUTPUT },
  txtz_output: { fields: TXT_OUTPUT },
  htmlz_output: {
    fields: [
      choice('htmlz_css_type', 'How to handle CSS', { uiData: 'css_choices' }),
      choice('htmlz_class_style', 'How to handle CSS classes', {
        uiData: 'sheet_choices',
      }),
      check(
        'htmlz_title_filename',
        'Use book title as the filename for the HTML file',
      ),
    ],
  },
  snb_output: {
    fields: [
      check('snb_insert_empty_line', 'Insert empty line between paragraphs'),
      check(
        'snb_dont_indent_first_line',
        "Don't indent the first line for each paragraph",
      ),
      check('snb_hide_chapter_name', 'Hide chapter name'),
      check('snb_full_screen', 'Optimize for full-screen mode'),
    ],
  },
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

// }}}
