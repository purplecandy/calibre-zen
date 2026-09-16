# calibre-zen

<img align="left" src="resources/images/lt.png" height="180" width="180"/>

A modern calibre for people who love ebooks.

calibre-zen rethinks calibre's interface so the hard things get easy and the easy things get trivial. Same library manager, far less friction.

It installs as a separate app, so **calibre stays untouched**. Run both at once. Your libraries, settings and plugins do not move.

[Website](https://zen.purplecandy.dev) · [Demo](https://youtu.be/Lc22AfF9u2c) · [Releases](https://github.com/purplecandy/calibre-zen/releases)

<br clear="left"/>

![calibre-zen](screenshots/library.png)

---

## Status

macOS public preview. Windows and Linux are not built yet.

This is early access. The interface has had a full overhaul, so expect some bugs. Back up your library before doing anything destructive.

**Bummer:** the self-signed build apparently cannot be opened directly on macOS. I am trying to figure it out and will update shortly. In the meantime you can build it yourself, or follow the repo for updates.

### Roadmap

- The ebook reader
- Easier metadata editing and the other common operations
- Reading stats out of the box
- More to follow

## Install

The macOS build is **not signed or notarised yet**, so macOS will block it on first launch. Opening it takes a few extra steps:

1. Download the latest build from [Releases](https://github.com/purplecandy/calibre-zen/releases)
2. Drag **calibre-zen** into your **Applications** folder. This step matters, Gatekeeper behaves differently if you run it from Downloads
3. Right click the app and choose **Open**. Do not double click it
4. A warning appears saying the developer cannot be verified. Dismiss it
5. Open **System Settings → Privacy & Security**, scroll to the Security section, and you will see a line about calibre-zen being blocked. Click **Open Anyway**
6. Confirm with Touch ID or your password

You only need to do this once. After that it opens normally.

If macOS says the app is damaged and should be moved to the Trash, that is the quarantine attribute rather than a real problem. Clear it with:

```
xattr -dr com.apple.quarantine /Applications/calibre-zen.app
```

calibre-zen uses its own config directory, single-instance lock, IPC socket and bundle identifier, so it installs beside calibre rather than on top of it. Its command line tools are prefixed `zen-`, so `zen-ebook-convert` and `ebook-convert` can coexist.

## What is different

- **Filter panel** in place of the tag browser: one screenful of rows at a time, counts beside each value, and a Reset that clears the lot
- **Split centre pane** with a preview of the selected book above the list, plus a Grid/Table switcher
- **Rebuilt book list** on tall row cards, while sorting, inline editing, column resizing and the header menu stay calibre's own
- **Cover grid** with three densities and every cover cropped to one shape
- **Status bar** that reports the current library, the sort, content server status and any running job
- **One token set** behind the whole stylesheet: colour ramp, radius scale, type scale, density
- **179 icons** redrawn as line glyphs, inked in the palette colour and re-inked when the palette changes
- **Six colour schemes** with match system, light, dim and dark, applied without a restart
- **Inter and Literata** bundled, so the interface reads the same on every machine

## How it works

Nothing here edits calibre.

The restyling lives in an overlay package that patches calibre from the outside. Custom widgets are built by composition and sit in front of calibre's existing models and signals, with the behaviour left where it was. That is what keeps upstream pullable: an idea that does not work out costs one environment variable rather than a merge conflict.

Every piece can be switched off:

```
CALIBRE_ZEN_FILTERS=0    # calibre's tag browser back
CALIBRE_ZEN_CENTRE=0     # calibre's centre pane back
CALIBRE_ZEN_STATUS=0     # calibre's status bar back
```

## Building

See [BUILDING.md](BUILDING.md), which also covers why a shipped calibre cannot simply be reskinned.

## Contributing

Issues and pull requests are welcome. Bug reports about calibre itself belong [upstream](https://github.com/kovidgoyal/calibre); anything about the interface belongs here.

## Licence

GPL-3.0, same as calibre.

## Credits

calibre is built by [Kovid Goyal](https://calibre-ebook.com) and this fork would not exist without it. calibre-zen is not affiliated with or endorsed by the calibre project.

### Third party

- [Tabler Icons](https://tabler.io/icons) by Paweł Kuna, MIT licence. The icon set behind every line glyph in the interface
- [Inter](https://rsms.me/inter/) by Rasmus Andersson, SIL Open Font Licence 1.1
- [Literata](https://github.com/googlefonts/literata) by TypeTogether, SIL Open Font Licence 1.1

### Note

I used AI for prototyping and the mechanical parts of the migration. The design decisions, the architecture and the review are mine.
