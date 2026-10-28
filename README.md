# Slaython

[![PyPI](https://img.shields.io/pypi/v/slaython)](https://pypi.org/project/slaython/)
[![Python](https://img.shields.io/pypi/pyversions/slaython)](https://pypi.org/project/slaython/)
[![tests](https://github.com/memoliertorerr/Slaython/actions/workflows/tests.yml/badge.svg)](https://github.com/memoliertorerr/Slaython/actions/workflows/tests.yml)

**Python, but the keywords are gen-z slang.** Slaython runs on the normal
Python interpreter, so every Python library works in it. Python can import
Slaython files and Slaython can import Python files.

```python
outta random pullup choice

deadass FITS = ["ate", "slay"]

blueprint Bestie:
    cook __init__(mee, name):
        mee.name = name

    cook rate(mee, fit):
        fr fit in FITS:
            serve f"{mee.name} ate that, no cap"
        ornah fr fit literally ghosted:
            serve f"{mee.name} got ghosted"
        ornah:
            serve f"{mee.name} is lowkey mid rn"

doomscroll fit in ["ate", ghosted, "mid"]:
    yap(Bestie(choice(["mia", "kai"])).rate(fit))
```

**Docs:** https://memoliertorerr.github.io/Slaython/docs/ ·
**Playground:** https://memoliertorerr.github.io/Slaython/

## Install

Slaython is on [PyPI](https://pypi.org/project/slaython/):

```sh
pip install slaython
```

Needs Python 3.10 or newer, nothing else. That gives you the `slaython` and
`slay` commands. To work on Slaython itself, clone the repo and run
`pip install -e .` instead.

## Run it

```sh
slaython examples/fizzbuzz.slay      # run a file (also: slay, python -m slaython)
slaython                             # interactive REPL
slaython -c 'yap("hi bestie")'       # run a snippet
slaython test                        # run test_*.slay files and vibecheck blocks
slaython glowup                      # swap leftover Python keywords for slang
slaython learn                       # interactive tutorial
slaython translate file.slay         # print the Python version
slaython slayify file.py             # turn Python into Slaython
slaython autoimport on               # let plain python import .slay files
slaython keywords                    # print the slang sheet
```

## Playground

Try Slaython in your browser, nothing to install:
https://memoliertorerr.github.io/Slaython/

It runs the real `slaython` package on [Pyodide](https://pyodide.org)
(Python compiled to WebAssembly). Write code, press Run (Ctrl/Cmd+Enter),
switch to the Python tab to see the translation, pick an example, or press
Share to get a link that carries your code.

Switch to **Translate** for a live translator: type Slaython on one side
and the Python appears on the other as you type. **Swap** flips the
direction (Python to Slaython) and carries your code across.

Preview it locally (this also builds the docs from `docs/*.md`):

```sh
python tools/build_playground.py && python -m http.server -d _site
```

then open http://localhost:8000 (docs at http://localhost:8000/docs/). The `pages` workflow publishes it on every
push to `main`. Anything in `slaython/` must stick to the standard library,
because the playground loads no other packages.

## Keywords

| Slaython | Python | Why |
|---|---|---|
| `nocap` / `cap` | `True` / `False` | no cap = no lie; cap = a lie |
| `ghosted` | `None` | nothing is there anymore |
| `and` | `and` | stays plain Python |
| `orr` | `or` | this orr that |
| `nah` | `not` | flips it to the opposite |
| `literally` | `is` | `x literally ghosted` = `x is None` |
| `in` | `in` | stays plain Python |
| `fr` | `if` | "for real?" |
| `ornah fr` | `elif` | or nah... but for real? |
| `ornah` | `else` | ...or nah |
| `doomscroll` | `for` | goes through items one by one |
| `lockedin` | `while` | stays locked in while the condition holds |
| `dip` | `break` | dip out of the loop |
| `anyways` | `continue` | skip the rest, move on |
| `chill` | `pass` | do nothing on purpose |
| `cook` | `def` | cook up a function |
| `serve` | `return` | serve what you cooked |
| `nohead` | `lambda` | no head, no name |
| `drop` | `yield` | drops values one at a time |
| `blueprint` | `class` | objects are copies of the blueprint |
| `shoot` | `try` | shoot your shot |
| `fumble` | `except` | what runs when the code fumbles |
| `periodt` | `finally` | always gets the last word |
| `yeet` | `raise` | yeet an error |
| `ongod` | `assert` | on god, this is true |
| `pullup` | `import` | pull up a module |
| `outta` | `from` | `outta math pullup sqrt` |
| `aka` | `as` | another name |
| `linkup` | `with` | link up with a resource, then part ways |
| `cancel` | `del` | remove it |
| `viral` | `global` | visible everywhere |
| `mutuals` | `nonlocal` | shared with the outer function |
| `lowkey` | `async` | runs quietly in the background |
| `holdup` | `await` | wait until it's done |
| `spill` | `match` | spill what's in the value |
| `pov` | `case` | each case is a "POV:" scenario |

Plain Python keywords still work too, so you can mix styles or migrate a
file bit by bit.

## Builtins

| Slaython | Python | |
|---|---|---|
| `yap()` | `print()` | yap to the console |
| `hmu()` | `input()` | ask the user to hit you up |
| `og()` | `super()` | call the original (parent) class |
| `goat()` | `max()` | greatest of all time |
| `flop()` | `min()` | the flop of the bunch |
| `tierlist()` | `sorted()` | rank everything |
| `whoisyou()` | `type()` | who even are you? |
| `giving()` | `isinstance()` | `giving(x, int)`: it's giving int |
| `skillissue` | `Exception` | the base error type |
| `touchgrass()` | `exit()` | quit and go outside |
| `mee` | `self` | the object talking about itself |
| `howlongisit()` | `len()` | how long is it? |
| `lowkeysus(x)` | debug print | prints `lowkeysus line 12: x = 42` and returns `x` |
| `bedrot(s)` | `time.sleep(s)` | do nothing for a while |
| `headzortailz()` | random `True`/`False` | flip a coin |
| `pickone(items)` | `random.choice(items)` | just pick one |
| `bruh()` | `breakpoint()` | stop here and open the debugger |
| `@corememory` | `@functools.cache` | the function remembers its answers |
| `squad(a, b)` | `asyncio.gather(a, b)` | run lowkey tasks together |

Helpers (`lowkeysus`, `bedrot`, `headzortailz`, `pickone`, `corememory`,
`squad`) only count when you call them or use them as a decorator, so a
variable called `squad` is still just a variable.

## Syntax Python doesn't have

```python
# run a block n times
runitfoo 3:
    yap("slay")

# constants: assigning MAX_LIKES again anywhere in the file is an error
deadass MAX_LIKES = 1_000

# yeet a plain message, it becomes an error
fr likes < 0:
    yeet "likes can't be negative"
```

`deadass` is checked when the file is translated: reassigning, augmenting
(`+=`) or `cancel`-ing the name anywhere in the same file is a syntax
error. Other modules can still change it at run time, like any Python name.

```python
# data classes: __init__, repr and == for free
lore Post:
    caption: str
    likes: int = 0

lore Point(frozen=nocap):      # dataclass options go in the header
    x: int

# enums: a fixed set of named values, numbered for you
gang Mood: ATE, MID, COOKED

gang Size:
    SMALL
    BIG, HUGE

# pipes: x |> f is f(x), and x |> f(y) is f(x, y)
feed |> tierlist(key=nohead p: p.likes) |> howlongisit

# retry a flaky block up to 3 times before fumble runs
shoot 3:
    data = fetch(url)
fumble ConnectionError:
    data = ghosted

# time a block (prints "speedrun line 12: 0.042s", or use a label)
speedrun "ranking":
    ranked = tierlist(feed)

# runs only when the file is run directly, not when it's pulled up
maincharacter:
    main()

# a test that lives next to the code; only `slaython test` runs it
vibecheck "double works":
    ongod double(2) == 4

# I don't care: run a block and ignore that error (`idc:` ignores any error)
idc FileNotFoundError:
    cleanup("old.txt")
```

Details:

- `|>` binds tighter than comparisons and `orr`/`and`, like in Elixir:
  `a |> f == b` is `f(a) == b`.
- `shoot n:` only retries errors that its `fumble` catches (any error if
  there's no `fumble`). `periodt` runs once at the end, not per try.
  `dip`/`anyways` can't go straight inside a `shoot n:` block.
- `lore` and `gang` blueprints can have methods like any blueprint.
  `lore` can extend another `lore`.
- `lore`, `gang`, `speedrun`, `vibecheck` and `maincharacter` only count at
  the start of a line, so you can still use them as names elsewhere.

See [`examples/feed_app.slay`](https://github.com/memoliertorerr/Slaython/blob/main/examples/feed_app.slay) for all of these in one
small program.

## Your own words

A project can add its own words in `pyproject.toml`. They work next to the
built-in ones in every `.slay` file under that folder (and in the REPL or
`-c` when you run from there):

```toml
[tool.slaython.words]
frfr = "if"          # a Python keyword or builtin...
vibe = "doomscroll"  # ...or an existing Slaython word
spit = "print"
```

New words can't reuse a word Slaython already has, so every project still
reads the same built-in words the same way.

## Working with Python

**Python → Slaython.** Anything Python can import, Slaython can `pullup`:

```python
pullup numpy aka np
outta pathlib pullup Path
```

**Slaython → Python.** Run `import slaython` once, and after that Python
can import `.slay` files and packages (`__init__.slay`) like normal modules:

```python
import slaython
import my_module            # loads my_module.slay
from squadpkg import rank   # squadpkg/__init__.slay
```

To skip the `import slaython` line entirely, run `slaython autoimport on`
(or `--user` without admin rights). It adds a small `.pth` file to
site-packages so every Python run can import `.slay` files. Undo it with
`slaython autoimport off`.

**Inline.** You can run Slaython code from inside Python:

```python
from slaython import slay, slay_eval, transpile, slayify

slay('yap("hi from slaython")')
slay_eval("[x * 2 doomscroll x in range(3)]")   # [0, 2, 4]
transpile("fr x: serve nocap")                  # 'if x: return True'
slayify("def f(): return None")                 # 'cook f(): serve ghosted'
```

**Jupyter.** To write whole notebooks in Slaython, install the kernel:

```sh
pip install "slaython[jupyter]"
slaython kernel install
```

Then pick **Slaython** as the kernel in Jupyter (Notebook, Lab or VS Code).
Every cell is Slaython, and IPython extras still work: `%time`, `!ls`,
`yap?` for help, Tab completion (slang included), and the last line of a
cell shows its value. `slaython kernel list` / `remove` manage it, and
`--user`, `--sys-prefix` or `--prefix PATH` pick where it goes.

In a normal Python notebook you can also `%load_ext slaython` and start a
cell with `%%slay`.

See [`examples/interop`](https://github.com/memoliertorerr/Slaython/blob/main/examples/interop) for both directions.

## Testing

`slaython test` finds `test_*.slay` and `*_test.slay` files, runs every
function whose name starts with `test` (and `test` methods of `Test...`
blueprints, async ones included), and prints a W or an L for each:

```
$ slaython test examples/testing
W examples/testing/test_feed.slay::test_rank
W examples/testing/test_feed.slay::test_ratio
...
4 W, 0 L in 0.01s: all W, no cap
```

Use `ongod` to check things. Add `-v` to see full tracebacks for Ls.
`vibecheck "name":` blocks in any `.slay` file are picked up too.

## Lint

`slaython lint` catches mistakes before you run anything: undefined names
(with a "did you mean"), unused `pullup`s and variables, unreachable code,
`literally` against a literal, `== ghosted`, `fumble` blocks that swallow
everything, mutable default arguments and more. Messages use the
Slaython words.

```sh
slaython lint                      # every .slay file under this folder
slaython lint src/ app.slay        # specific files or folders
slaython lint --select SL1,SL201   # only these checks (codes or prefixes)
slaython lint --ignore SL103       # everything except these
slaython lint --codes              # list every check
```

Each problem prints as `path:line:col: CODE message`; it exits 1 when it
finds something. Add `# lint: ignore` (or `# lint: ignore[SL201]`) at the
end of a line to silence it.

## Glow up

`slaython glowup` swaps plain Python left in `.slay` files for slang
(`if` becomes `fr`, `self` becomes `mee`, `if __name__ == "__main__":`
becomes `maincharacter:` and so on):

```sh
slaython glowup              # every .slay file under this folder
slaython glowup --diff src/  # show what would change
slaython glowup --check      # for CI: exit 1 if anything needs a glowup
```

## Errors in slang

Tracebacks show your `.slay` lines, with carets in the right columns, plus
a short explanation:

```
KeyError: 'k'
real talk: that key got ghosted. it's not in the dict
```

Syntax errors also translate keywords. For example, `expected 'except' or
'finally' block` adds `('except' is 'fumble' in Slaython, ...)`. Turn the
explanations off with `slaython --no-vibes ...` or `SLAYTHON_VIBES=0`.

## More

- **Line numbers are kept.** Translation never adds or removes lines, so
  line N of your `.slay` file is line N of the generated Python.
- **Two-way translation.** `slaython translate` and `slaython slayify`
  turn whole files into each other. `slayify` warns you when one of your
  Python names (such as a variable called `drop`) is a Slaython word.
- **REPL.** Run `slaython` with no file. Type `slang` there for the sheet.
- **VS Code.** [`editors/vscode`](https://github.com/memoliertorerr/Slaython/blob/main/editors/vscode) adds highlighting, hovers
  that show the Python for each word, snippets (`cook`, `blueprint`, `fr`,
  `shoot`, `lore`, `vibecheck`, ...) and commands: Slaython: Run File (also a
  play button), Show Python, and Run Tests. Set `slaython.command` to
  `python -m slaython` if the `slaython` script isn't on your PATH.

## Things to know

- **Slang words are reserved.** A variable named `cap` or `drop` turns into
  a keyword. Two exceptions: attribute access (`df.drop(...)`) and keyword
  arguments (`reset_index(drop=nocap)`) are never translated, so Python
  libraries keep working.
- **`spill`, `pov` and `runitfoo` only count at the start of a line**
  ending in `:`, so `spill = 3` is still a normal variable.
- **`slaython translate` on files with `shoot n:` or `|>`** rebuilds the
  Python from the syntax tree, so comments and blank lines are dropped in
  that output. Running the file is not affected.
- If a module exists as both `foo.py` and `foo.slay` in the same folder,
  `foo.py` wins.

## Development

```sh
python -m unittest discover -s tests -t .     # tests
python tools/gen_vscode_grammar.py            # regenerate the VS Code extension data
```

To release a new version: bump `__version__` in
[`slaython/__init__.py`](https://github.com/memoliertorerr/Slaython/blob/main/slaython/__init__.py), push, then publish a GitHub
release tagged `v` plus that version (for example `v0.3.0`). The `publish`
workflow runs the tests, builds the package and uploads it to PyPI.

The word list lives in [`slaython/keywords.py`](https://github.com/memoliertorerr/Slaython/blob/main/slaython/keywords.py).
Change a word there, and the translator, the CLI sheet and the VS Code
extension all follow.

## License

[MIT](https://github.com/memoliertorerr/Slaython/blob/main/LICENSE)
