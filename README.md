# Slaython 💅

**Python, but the keywords are gen-z slang.** Slaython runs on the normal
Python interpreter, so every Python library works in it. Python can import
Slaython files and Slaython can import Python files.

```python
outta random pullup choice

blueprint Bestie:
    cook __init__(self, name):
        self.name = name

    cook rate(self, fit):
        fr fit canon ["ate", "slay"]:
            serve f"{self.name} ate that, no cap"
        ornah fr fit literally ghosted:
            serve f"{self.name} got ghosted"
        ornah:
            serve f"{self.name} is lowkey mid rn"

doomscroll fit canon ["ate", ghosted, "mid"]:
    yap(Bestie(choice(["mia", "kai"])).rate(fit))
```

## Install

```sh
pip install .            # from a clone of this repo
```

Needs Python 3.10 or newer. Nothing else is required.

## Run it

```sh
slaython examples/fizzbuzz.slay      # run a file (also: slay, python -m slaython)
slaython                             # interactive REPL
slaython -c 'yap("hi bestie")'       # run a snippet
slaython translate file.slay         # print the Python version
slaython slayify file.py             # turn Python into Slaython
slaython keywords                    # print the slang sheet
```

## The slang sheet

| Slaython | Python | Why |
|---|---|---|
| `nocap` / `cap` | `True` / `False` | no cap = no lie; cap = a lie |
| `ghosted` | `None` | nothing is there anymore |
| `collab` | `and` | both sides have to collab |
| `orwhatever` | `or` | this one, or whatever that is |
| `nah` | `not` | flips it to the opposite |
| `literally` | `is` | `x literally ghosted` = `x is None` |
| `canon` | `in` | `x canon items` = x is part of items (`nah canon` = not in) |
| `fr` | `if` | "for real?" |
| `ornah fr` | `elif` | or nah... but for real? |
| `ornah` | `else` | ...or nah |
| `doomscroll` | `for` | goes through items one by one |
| `lockin` | `while` | stays locked in while the condition holds |
| `dip` | `break` | dip out of the loop |
| `anyways` | `continue` | skip the rest, move on |
| `chill` | `pass` | do nothing on purpose |
| `cook` | `def` | cook up a function |
| `serve` | `return` | serve what you cooked |
| `npc` | `lambda` | a function with no name |
| `drop` | `yield` | drops values one at a time |
| `blueprint` | `class` | objects are copies of the blueprint |
| `tryna` | `try` | tryna do something risky |
| `crashout` | `except` | what runs when the code crashes out |
| `periodt` | `finally` | always gets the last word |
| `yeet` | `raise` | yeet an error |
| `ong` | `assert` | on god, this is true |
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
| `yap()` | `print()` | yap to the console |
| `hmu()` | `input()` | ask the user to hit you up |
| `og()` | `super()` | call the original (parent) class |

Plain Python keywords still work, so you can mix styles or migrate a file
bit by bit.

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

**Inline.** You can run Slaython code from inside Python:

```python
from slaython import slay, slay_eval, transpile, slayify

slay('yap("hi from slaython")')
slay_eval("[x * 2 doomscroll x canon range(3)]")   # [0, 2, 4]
transpile("fr x: serve nocap")                      # 'if x: return True'
slayify("def f(): return None")                     # 'cook f(): serve ghosted'
```

See [`examples/interop`](examples/interop) for both directions.

## Features beyond Python

- **Errors in slang.** Tracebacks show your `.slay` lines, with carets in
  the right columns, plus a short explanation:
  ```
  KeyError: 'k'
  💀 that key got ghosted. it's not in the dict
  ```
  Syntax errors also translate keywords. For example, `expected 'except'
  or 'finally' block` adds `('except' is 'crashout' in Slaython, ...)`.
- **Line numbers are kept.** Translation only swaps words, so line N of
  your `.slay` file is line N of the generated Python.
- **Two-way translation.** `slaython translate` and `slaython slayify`
  turn whole files into each other. `slayify` warns you when one of your
  Python names (such as a variable called `drop`) is a Slaython keyword.
- **REPL.** Run `slaython` with no file. Type `slang` there for the keyword
  sheet.
- **VS Code highlighting.** See [`editors/vscode`](editors/vscode).

## Things to know

- **Slang words are reserved.** A variable named `cap` or `drop` turns into
  a keyword. Two exceptions: attribute access (`df.drop(...)`) and keyword
  arguments (`reset_index(drop=nocap)`) are never translated, so Python
  libraries keep working.
- **`spill` and `pov` are soft keywords**, like `match` and `case` in Python.
  They only count as keywords at the start of a `spill x:` or `pov ...:`
  line, so `spill = 3` is still a normal variable.
- **f-strings on Python 3.10 and 3.11:** slang inside `{...}` is not
  translated, because those versions read an f-string as one token. Use
  Python keywords inside f-string braces there, or use Python 3.12+.
- If a module exists as both `foo.py` and `foo.slay` in the same folder,
  `foo.py` wins.

## Development

```sh
python -m unittest discover -s tests -t .     # tests
python tools/gen_vscode_grammar.py            # regenerate the VS Code grammar
```

The keyword table lives in [`slaython/keywords.py`](slaython/keywords.py).
Change a word there, and the translator, the CLI sheet and the VS Code
grammar all follow.
