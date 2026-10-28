# Tools

Slaython comes with a command line tool, `slaython` (also `slay`), that
runs code and does everything around it: tests, formatting, linting and
translating. This page covers each tool, then lists every command.

## slaython test

`slaython test` finds and runs your tests. It looks for:

- files named `test_*.slay` or `*_test.slay`, and runs every function whose
  name starts with `test`, plus the `test` methods of blueprints whose name
  starts with `Test`;
- [`vibecheck "name":`](guide.md#vibecheck) blocks in any `.slay` file.

A test passes (W) if it finishes, and fails (L) if it raises an error. Use
`ongod` to check things. Async (`lowkey`) tests work too.

```slay norun
# test_feed.slay
cook rank(posts):
    serve tierlist(posts, reverse=nocap)

cook test_rank():
    ongod rank([1, 3, 2]) == [3, 2, 1]

blueprint TestFeed:
    cook test_empty(mee):
        ongod rank([]) == []

vibecheck "biggest first":
    ongod rank([5, 9])[0] == 9
```

```text
$ slaython test
W test_feed.slay::test_rank
W test_feed.slay::TestFeed.test_empty
W test_feed.slay::vibecheck 'biggest first'

3 W, 0 L in 0.01s: all W, no cap
```

```sh
slaython test                    # everything under this folder
slaython test tests/ app.slay    # specific folders or files
slaython test -v                 # full tracebacks for each L
```

It exits with 0 when every test passes, 1 when any fails, and 5 when it
finds no tests.

## slaython fmt

`slaython fmt` formats `.slay` files so they all follow one style. With no
paths, it formats every `.slay` file under the current folder.

```sh
slaython fmt                 # format every .slay file under this folder
slaython fmt src/ app.slay   # specific folders or files
slaython fmt --diff          # show what would change, change nothing
slaython fmt --check         # for CI: exit 1 if any file needs formatting
slaython fmt - < app.slay    # format stdin, print the result
```

It only changes whitespace: 4 spaces per indentation level, blank lines,
and the spaces between words and symbols. Strings and comments stay as they
are. Before it writes a file, it checks that the result has the same code
and still compiles. If not, it leaves the file alone and tells you.

## slaython lint

`slaython lint` checks `.slay` files for mistakes without running them. It
catches things like names that were never defined, `pullup`s you never
use, code after `serve` that can never run, and `== ghosted` where you want
`literally ghosted`.

```sh
slaython lint                      # every .slay file under this folder
slaython lint src/ app.slay        # specific folders or files
slaython lint --codes              # list every check and its code
slaython lint --select SL1,SL201   # only these checks (codes or prefixes)
slaython lint --ignore SL103       # every check except these
```

Each problem prints as `path:line:col: CODE message`. It exits with 0 when
the files are clean and 1 when it finds problems, so you can run it in CI.
To silence a line, end it with `# lint: ignore`, or
`# lint: ignore[SL101]` for just one check.

## slaython glowup

`slaython glowup` swaps the plain Python left in your `.slay` files for
slang: `if` becomes `fr`, `self` becomes `mee`, and
`if __name__ == "__main__":` becomes `maincharacter:`.

```sh
slaython glowup              # every .slay file under this folder
slaython glowup src/         # specific folders or files
slaython glowup --diff src/  # show what would change, change nothing
slaython glowup --check      # for CI: exit 1 if anything needs a glowup
```

It only changes Python keywords and builtins. It leaves your names, strings
and comments alone.

## slaython translate

`slaython translate` prints the Python version of a Slaython file. Use it to
see what your code turns into.

```sh
slaython translate app.slay           # print to the terminal
slaython translate app.slay -o app.py # write a file
```

The output keeps your line numbers, comments and blank lines. Files that use
`shoot n:` or `|>` are the exception: Slaython rebuilds those from the
syntax tree, which drops comments and blank lines.

The translated code can still call into Slaython for some features
(`lore`, `gang`, `speedrun`, `shoot n:`, `lowkeysus` and the random
helpers), so it needs Slaython installed to run. For Python that runs
anywhere, use [`slaython build`](#slaython-build).

## slaython build

`slaython build` turns Slaython into plain Python that runs without
Slaython installed. Use it to ship code to people or servers that don't
have Slaython.

```sh
slaython build                  # this folder, into build/py
slaython build src -o out       # pick the source and output folders
slaython build app.slay -o out  # a single file
slaython build --clean          # empty the output folder first
```

Every `.slay` file becomes a `.py` file at the same path inside the output
folder, and other files (`.py` modules, data files) are copied over. The few
features that need help at run time (`lore`, `gang`, `lowkeysus`, ...) get a
small `slaython_runtime.py` module next to the code, so nothing has to be
installed.

## slaython slayify

`slaython slayify` goes the other way: it turns a Python file into
Slaython.

```sh
slaython slayify app.py               # print to the terminal
slaython slayify app.py -o app.slay   # write a file
```

If your Python code uses a Slaython word as a name, such as a variable
called `drop` or `cap`, `slayify` warns you with the file, line and column.
Rename those, or they turn into keywords.

## slaython learn

`slaython learn` is an interactive tutorial in the terminal. See
[Getting started](getting-started.md#learn-the-language-slaython-learn).

```sh
slaython learn          # pick up where you left off
slaython learn 3        # jump to lesson 3
slaython learn --list   # every lesson and what you finished
slaython learn --reset  # start over
```

## Jupyter kernel

`slaython kernel install` adds a Slaython kernel to Jupyter. Then pick
**Slaython** as the notebook kernel, and every cell runs as Slaython. See
[Jupyter and IPython](python.md#the-slaython-kernel) for details.

```sh
slaython kernel install              # for every user of this Python
slaython kernel install --user       # just for you
slaython kernel install --sys-prefix # inside the current virtual environment
slaython kernel list                 # show installed Slaython kernels
slaython kernel remove               # remove it again
```

## VS Code

The Slaython extension for VS Code lives in
[`editors/vscode`](https://github.com/memoliertorerr/Slaython/tree/main/editors/vscode).
It adds:

- **Highlighting** for every Slaython word, `|>` and the new syntax.
- **Hovers**: hover a word to see the Python it stands for and why.
- **Snippets** for blocks: type `cook`, `blueprint`, `fr`, `doomscroll`,
  `shoot`, `lore`, `vibecheck` and so on, or the Python keyword.
- **Commands** in the Command Palette: *Slaython: Run File* (also a play
  button in the editor title bar), *Slaython: Show Python* and
  *Slaython: Run Tests*.

The commands need Slaython installed. If the `slaython` command isn't on
your PATH, set the `slaython.command` setting to `python -m slaython`.

To install it from a clone of the repo, copy the folder into your
extensions folder and restart VS Code:

```sh
cp -r editors/vscode ~/.vscode/extensions/memoliertorerr.slaython
```

## pre-commit hooks

Projects that use [pre-commit](https://pre-commit.com) can run Slaython's
tools before each commit:

```yaml
- repo: https://github.com/memoliertorerr/Slaython
  rev: v0.4.0
  hooks:
    - id: slaython-glowup
    - id: slaython-fmt
    - id: slaython-lint
    - id: slaython-test
```

## The playground

The [playground](../) runs Slaython in the browser, with nothing to install.
It has an editor, a Python tab that shows the translation, the example
programs and the keyword sheet. Share makes a link that carries your code
inside the link itself, so nothing is uploaded.

## Command reference

| Command | What it does |
|---|---|
| `slaython FILE [ARGS...]` | run a `.slay` file (`slay` and `python -m slaython` work too) |
| `slaython run FILE [ARGS...]` | same as above |
| `slaython` | start the REPL (also `slaython repl`) |
| `slaython -c CODE [ARGS...]` | run a snippet |
| `slaython - [ARGS...]` | run code piped in on stdin |
| `slaython test [PATHS...] [-v]` | run tests and `vibecheck` blocks |
| `slaython fmt [PATHS...] [--check\|--diff]` | format `.slay` files |
| `slaython lint [PATHS...] [--select\|--ignore CODES]` | check `.slay` files for mistakes |
| `slaython glowup [PATHS...] [--check\|--diff]` | swap leftover Python keywords for slang |
| `slaython translate FILE [-o OUT]` | Slaython to Python |
| `slaython build [SRC] [-o OUT] [--clean]` | Slaython to plain Python that runs without Slaython |
| `slaython slayify FILE [-o OUT]` | Python to Slaython |
| `slaython learn [N] [--list\|--reset]` | interactive tutorial |
| `slaython autoimport on\|off\|status [--user]` | let plain `python` import `.slay` files |
| `slaython kernel install\|list\|remove` | manage the Slaython kernel for Jupyter |
| `slaython keywords` | print the keyword sheet |
| `slaython version` | print the Slaython and Python versions |
| `slaython help` | print the command list |

Put `--no-vibes` before the command (`slaython --no-vibes app.slay`), or set
`SLAYTHON_VIBES=0`, to turn off the slang notes under errors.
