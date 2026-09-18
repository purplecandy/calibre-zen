#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
"""
Write the WiX source for the calibre-zen .msi.

calibre-zen's take on bypy/windows/wix.py: walk the staged install tree,
emit one Component per file (and the Run-dialog App Paths entries for the
fork's launchers), and fill wix-template.xml's @...@ fields. package.ps1
then runs `wix build` on the result. Run with the bundle's calibre-debug:

    calibre-debug -e wix.py -- <stage> <out-dir> KEY=VALUE...

where the KEY=VALUE pairs are the template's fields other than
@COMPONENTS@ and the three *_EXE_ID ones, which are derived here. The
bundle runs Python with -OO, so nothing here is an assert.
"""

import os
import sys
from itertools import count
from xml.sax.saxutils import escape, quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))

# The executables a user may type into the Run dialog. Never the frozen
# upstream names: registering calibre.exe here would point calibre's own
# App Paths entry at this tree.
LAUNCHERS = ('calibre-zen.exe', 'zen-ebook-viewer.exe', 'zen-ebook-edit.exe')


def components(stage):
    ids = count()
    file_ids = {}
    out = []

    def walk(path, depth):
        pad = '\t' * depth
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            fid = next(ids)
            if os.path.isdir(full):
                out.append(f'{pad}<Directory Id="dir_{fid}" FileSource={quoteattr(full)} Name={quoteattr(name)}>')
                walk(full, depth + 1)
                out.append(f'{pad}</Directory>')
                continue
            file_ids[os.path.relpath(full, stage)] = fid
            checksum = ' Checksum="yes"' if name.lower().endswith('.exe') else ''
            out.append(f'{pad}<Component Id="component_{fid}" Feature="MainApplication" Guid="*">')
            out.append(f'{pad}\t<File Id="file_{fid}" Source={quoteattr(full)} Name={quoteattr(name)} ReadOnly="yes" KeyPath="yes"{checksum}/>')
            if depth == 0 and name in LAUNCHERS:
                # https://learn.microsoft.com/windows/win32/shell/app-registration
                key = rf'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}'
                out.append(f'{pad}\t<RegistryValue Root="HKLM" Key={quoteattr(key)} Value="[#file_{fid}]" Type="string" />')
                out.append(f'{pad}\t<RegistryValue Root="HKLM" Key={quoteattr(key)} Name="Path" Value="[APPLICATIONFOLDER]" Type="string" />')
            out.append(f'{pad}</Component>')

    walk(stage, 0)
    return '\n'.join('\t\t\t' + line for line in out), file_ids


def main():
    args = [a for a in sys.argv[1:] if a != '--']
    if len(args) < 2:
        raise SystemExit(__doc__)
    stage, out_dir = os.path.abspath(args[0]), os.path.abspath(args[1])
    fields = dict(a.split('=', 1) for a in args[2:])
    if not os.path.isdir(stage):
        raise SystemExit(f'{stage} is not a directory')
    os.makedirs(out_dir, exist_ok=True)

    body, file_ids = components(stage)
    fields['COMPONENTS'] = body
    for field, exe in (('MAIN_EXE_ID', LAUNCHERS[0]), ('VIEWER_EXE_ID', LAUNCHERS[1]), ('EDITOR_EXE_ID', LAUNCHERS[2])):
        if exe not in file_ids:
            raise SystemExit(f'{exe} is not at the top of {stage}')
        fields[field] = f'file_{file_ids[exe]}'

    with open(os.path.join(HERE, 'wix-template.xml'), encoding='utf-8') as f:
        wxs = f.read()
    for key, value in fields.items():
        # Everything but the component block lands inside an attribute value.
        if key != 'COMPONENTS':
            value = escape(value, {'"': '&quot;'})
        wxs = wxs.replace(f'@{key}@', value)
    left = sorted({w for w in wxs.split('@')[1::2] if w.isupper()})
    if left:
        raise SystemExit(f'unfilled fields in wix-template.xml: {", ".join(left)}')

    wxs_path = os.path.join(out_dir, f'{fields["APP"]}.wxs')
    with open(wxs_path, 'w', encoding='utf-8') as f:
        f.write(wxs)
    print(f'    {len(file_ids)} files -> {wxs_path}')


if __name__ == '__main__':
    main()
