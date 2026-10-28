# Slaython for VS Code

Language support for [Slaython](https://github.com/memoliertorerr/Slaython)
(`.slay` files): Python, but the keywords are gen-z slang.

## Features

- **Highlighting** for every Slaython word, the `|>` pipe and the new syntax
  (`maincharacter`, `lore`, `gang`, `speedrun`, `vibecheck`, `runitfoo`, `deadass`).
- **Hovers.** Hover a word to see the Python it stands for and why. For example
  `fumble` shows `except`: "what runs when the code fumbles". Works for
  `ornah fr` (elif) and `|>` too.
- **Snippets** for the block constructs. Type the slang word (`cook`, `blueprint`,
  `fr`, `ornahfr`, `doomscroll`, `shoot`, `spill`, `lore`, `vibecheck`, ...) or the
  Python keyword (`def`, `class`, `if`, `for`, `try`, ...) and pick the snippet.
- **Commands** (Command Palette, `Slaython: ...`):
  - **Run File**: saves the file and runs `slaython <file>` in a terminal. Also
    the play button in the editor title bar of `.slay` files.
  - **Show Python**: opens the translated Python (`slaython translate`) beside
    the editor.
  - **Run Tests**: runs `slaython test` on the workspace folder.

## Settings

| Setting | Default | |
|---|---|---|
| `slaython.command` | `slaython` | How to run Slaython, e.g. `python -m slaython` or `"C:\My Python\python.exe" -m slaython`. Split on spaces; quote parts that contain spaces. |

The commands need Slaython installed (`pip install .` from the repo, Python 3.10+).
In untrusted workspaces, `slaython.command` is only read from your user settings.

## Install from source

Copy or link this folder into your extensions folder and restart VS Code:

```sh
# from the repo root
cp -r editors/vscode ~/.vscode/extensions/memoliertorerr.slaython
```

Or build a `.vsix` and install that:

```sh
cd editors/vscode
npx @vscode/vsce package --skip-license          # writes slaython-<version>.vsix
code --install-extension slaython-*.vsix
```

`--skip-license` is needed until the repo has a LICENSE file.

## Publishing (later)

1. Create the `memoliertorerr` publisher at
   <https://marketplace.visualstudio.com/manage> and an Azure DevOps personal
   access token with the **Marketplace (Manage)** scope.
2. `npx @vscode/vsce login memoliertorerr`
3. `npx @vscode/vsce publish --skip-license` from this folder.

Bump the version in `slaython/__init__.py` first; the generator copies it into
`package.json`. To also publish on Open VSX: `npx ovsx publish -p <token>`.

## Development

The word list lives in `slaython/keywords.py`. These files are generated from
it by `python tools/gen_vscode_grammar.py` (run from the repo root), so edit
the keyword table or the generator, not the JSON:

- `package.json`, `language-configuration.json`
- `syntaxes/slaython.tmLanguage.json` (grammar)
- `data/keywords.json` (hover data)
- `snippets/slaython.json`

`python tools/gen_vscode_grammar.py --check` fails when they are out of date.

Hand-written: `extension.js` (VS Code glue) and `lib/lookup.js` (word lookup,
hover text, command quoting; no VS Code API, so it runs in plain node). Tests:

```sh
node test/lookup.test.js       # lookup logic and generated data
node test/extension.test.js    # commands and hovers against a stubbed vscode module
```

To try changes, open this folder in VS Code and press F5 (Run Extension).
