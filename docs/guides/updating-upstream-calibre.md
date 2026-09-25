# Update the upstream calibre release

calibre-zen ships calibre's release binary with this fork's Python on top. Both must come from the same calibre release.

This guide covers the source merge, installer pin, checks, and pull request. It does not bump `zen_version`, which is the separate calibre-zen release number.

## 1. Start from the current fork branch

Use a clean worktree based on the latest `zen`. In these examples, replace `9.14.0` and `9.15.0` with the old and new releases.

```sh
old_version=9.14.0
new_version=9.15.0
git fetch origin zen
git fetch upstream tag "v$new_version"
git worktree add -b "wt/upstream-$new_version" "../calibre-upstream-$new_version" origin/zen
cd "../calibre-upstream-$new_version"
git status --short
```

Merge the **release tag**, never upstream `master`. The source must match the binary that packaging downloads.

```sh
git merge --no-commit --no-ff "v$new_version"
```

## 2. Resolve the fork identity conflict

`src/calibre/constants.py` is expected to conflict. Keep `__appname__ = 'calibre-zen'`, `zen_version`, and `zen_display_name` from the fork. Take the new upstream `numeric_version`. Leave `__version__` derived from `numeric_version`.

Check any other conflicts before staging. Keep the fork's hooks and identity changes, and take upstream's new behavior around them. The rules for files under `src/calibre/` are in [the overlay README](../../src/calibre_zen/README.md). In particular, styling changes stay in `src/calibre_zen/`.

```sh
git diff --name-only --diff-filter=U
git diff "v$new_version" -- src/calibre setup/install.py
```

Upstream may change native code or build inputs. The matching release binary already contains those changes. This fork does not build them or edit upstream `.c` and `.cpp` files.

```sh
git diff --stat "v$old_version" "v$new_version" -- bypy/sources.json setup/extensions.json 'src/calibre/**/*.c' 'src/calibre/**/*.cpp'
```

## 3. Pin the five installers

Use the repository's `purple-agent` GitHub account. Read each asset's name and `sha256:` digest from the upstream release.

```sh
gh auth switch --user purple-agent
gh release view "v$new_version" -R kovidgoyal/calibre --json assets --jq '.assets[] | [.name, .digest] | @tsv'
```

Update `packaging/upstream.json` with the new version, names, and digests for Linux x86_64, Linux arm64, macOS, Windows x64, and Windows portable. Keep the other fields. If upstream has removed its release assets, read the same digests from this repository's `upstream-<version>` mirror release and its `SHA256SUMS` file.

```sh
gh release view "upstream-$new_version" -R purplecandy/calibre-zen --json assets --jq '.assets[] | [.name, .digest] | @tsv'
```

The `numeric_version` in `src/calibre/constants.py` and the version in `packaging/upstream.json` must agree. Keep `zen_version` as it is unless you are also cutting a calibre-zen release.

## 4. Test with the matching calibre binary

`./zen-test` checks the installed calibre version before it starts. If your installed app is still on the old release, use the new release binary. The source worktree must be writable because calibre generates UI Python files on the first run.

On macOS, download the new image from calibre's archive, check it against the pinned digest, and run the suite from the mounted app:

```sh
runtime_dir=$(mktemp -d)
mkdir "$runtime_dir/mount"
curl -fL "https://download.calibre-ebook.com/$new_version/calibre-$new_version.dmg" -o "$runtime_dir/calibre-$new_version.dmg"
expected=$(python3 -c 'import json; print(json.load(open("packaging/upstream.json"))["assets"]["macos"]["sha256"])')
echo "$expected  $runtime_dir/calibre-$new_version.dmg" | shasum -a 256 -c -
hdiutil attach -nobrowse -readonly -quiet -mountpoint "$runtime_dir/mount" "$runtime_dir/calibre-$new_version.dmg"
debug="$runtime_dir/mount/calibre.app/Contents/MacOS/calibre-debug"
CALIBRE_ZEN_CALIBRE_DEBUG="$debug" ./zen-test
CALIBRE_DEVELOP_FROM="$PWD/src" "$debug" -c 'import compileall, os, sys; sys.exit(0 if compileall.compile_dir(os.environ["CALIBRE_DEVELOP_FROM"], quiet=1, workers=0) else 1)'
hdiutil detach -quiet "$runtime_dir/mount"
rm -r "$runtime_dir"
```

Run the lint and format checks with the Ruff version pinned in `.github/workflows/zen-ci.yml`. At the time of this guide, it is 0.16.8:

```sh
uvx ruff@0.16.8 check .
uvx ruff@0.16.8 format --check --diff src/calibre_zen packaging
```

If `git diff --check` reports whitespace introduced by the upstream tag, inspect the file before changing it. The 9.15.0 merge had trailing whitespace in upstream's `local-agent.md`; it was left as upstream shipped it.

## 5. Open the pull request

Review the staged diff, then commit with the required co-author trailer. Push the `wt/` branch. Use `-R` with `gh` because the repository's SSH host alias can keep it from finding the right GitHub repository.

```sh
git status --short
git add -A
git diff --cached --stat
git commit -m "Merge calibre $new_version into calibre-zen" -m "Co-authored-by: Nadeem Siddique <nadeem@kibibyte.in>"
git push -u origin "wt/upstream-$new_version"
```

Fill in `.github/pull_request_template.md` with the visible changes, trade-offs, and what needs a quick check. Open the PR against `zen` and request `purplecandy` as reviewer. Do not merge it yourself.

```sh
gh pr create -R purplecandy/calibre-zen --base zen --head "wt/upstream-$new_version" --title "Update calibre to $new_version" --body-file /path/to/pr-body.md --reviewer purplecandy
```

On the PR, check `zen ci`, CodeQL, and the Linux package jobs. The Linux jobs build archives, install them, and build Flatpaks. macOS and Windows packaging runs after a push to `zen` or a release tag, so those jobs are skipped on a PR.
