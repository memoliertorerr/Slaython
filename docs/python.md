# Working with Python

Slaython runs on the normal Python interpreter. Your Slaython code can use
any Python library, and your Python code can import Slaython files. This
page shows both directions, plus running Slaython from inside Python and in
Jupyter.

## Python libraries in Slaython

Anything Python can import, Slaython can `pullup`. That includes the
standard library and anything you installed with pip.

```slay
pullup json
outta pathlib pullup Path
outta statistics pullup mean aka average

yap(json.dumps({"vibe": "ate"}))
yap(Path("feed") / "posts.json")
yap(average([7, 8, 9]))
```

```slay norun
pullup numpy aka np
pullup pandas aka pd

df = pd.DataFrame({"user": ["mia", "kai"], "likes": [420, 12]})
yap(df.drop(columns=["likes"]).reset_index(drop=nocap))
```

That second example uses `drop` as a method name and as a keyword argument.
Slaython never translates a word after a dot (`df.drop`) or before a single
`=` inside a call (`drop=nocap`), so libraries that use slang words as names
keep working. The one case to watch is importing such a name directly:
`outta mylib pullup drop` reads `drop` as `yield`. Pull up the module and
use `mylib.drop(...)` instead.

## Slaython files in Slaython

A `.slay` file can `pullup` another `.slay` file, the same way Python files
import each other. Say you have two files in one folder:

```slay norun
# ranking.slay
outta statistics pullup mean

cook rank(scores):
    averages = {name: mean(vals) doomscroll name, vals in scores.items()}
    serve tierlist(averages, key=averages.get, reverse=nocap)
```

```slay norun
# app.slay
outta ranking pullup rank

yap(rank({"mia": [9, 10], "kai": [8, 9]}))
```

Run `slaython app.slay` and it finds `ranking.slay` next to it. Packages
work too: a folder with an `__init__.slay` file is a package, and relative
imports like `outta .ranking pullup rank` work inside it.

## Slaython files in Python

Run `import slaython` once. After that, Python can import `.slay` files and
packages like normal modules:

```python
import slaython

import ranking                  # loads ranking.slay
from squadpkg import rank       # loads squadpkg/__init__.slay

print(ranking.rank({"mia": [9, 10], "kai": [8, 9]}))
```

Slaython finds `.slay` files on `sys.path`, in the same order Python
searches for `.py` files. If a folder has both `foo.py` and `foo.slay`,
`foo.py` wins.

Errors raised inside an imported `.slay` file show the Slaython lines in the
traceback, with the same line numbers as your file.

### autoimport: skip the `import slaython` line

`slaython autoimport on` lets every Python run import `.slay` files, with no
`import slaython` needed:

```sh
slaython autoimport on          # turn it on (writes a small .pth file to site-packages)
slaython autoimport on --user   # use your user site-packages, if you have no admin rights
slaython autoimport status      # is it on?
slaython autoimport off         # remove it again
```

It works by adding a small `.pth` file that Python reads at startup. The
file never fails, so uninstalling Slaython can't break Python. Use
`--dir FOLDER` to put the file somewhere else, such as a virtual
environment's `site-packages`.

## Running Slaython inside Python

The `slaython` package has a few functions for running Slaython code from a
Python program:

```python
from slaython import slay, slay_eval, transpile, slayify, compile_slay

slay('yap("hi from slaython")')                   # run statements
slay_eval("[x * 2 doomscroll x in range(3)]")     # [0, 2, 4]
transpile("fr x: serve nocap")                    # 'if x: return True'
slayify("def f(): return None")                   # 'cook f(): serve ghosted'
code = compile_slay("yap(1 + 1)", "<mine>")       # a code object for exec()
exec(code)
```

- `slay(source)` runs Slaython statements in the caller's namespace, so
  the code can see and set your variables. Pass `globals` and `locals` to
  use other namespaces.
- `slay_eval(source)` evaluates one Slaython expression and returns its
  value.
- `transpile(source)` returns the Python source. `slayify(source)` goes
  the other way.
- `compile_slay(source, filename)` compiles to a code object, the same
  way `compile()` does for Python.

Here is a Python script that mixes both:

```python
import slaython

likes = [420, 12, 77]
slaython.slay("top = goat(likes)")
print(top)                                    # 420
print(slaython.slay_eval("likes |> howlongisit"))   # 3
```

## Jupyter and IPython

There are two ways to use Slaython in a notebook.

### The %%slay magic

Load the extension once per notebook, then start any cell with `%%slay`:

```python
%load_ext slaython
```

```python
%%slay
doomscroll n in range(3):
    yap(n, "slay")
```

`%slay` on one line evaluates a single expression and shows its value, like
a normal notebook cell:

```python
%slay [n * 2 doomscroll n in range(5)]
```

Cells share variables, so Python cells and `%%slay` cells can work on the
same data.

### The Slaython kernel

The Slaython kernel makes every cell a Slaython cell, with no magic needed.
Install it once:

```sh
slaython kernel install          # for every user of this Python
slaython kernel install --user   # just for you
```

Then pick **Slaython** as the kernel when you create a notebook, or change
the kernel of an open one. In a virtual environment, use
`slaython kernel install --sys-prefix`.

The kernel is IPython's kernel with Slaython on top, so `%magics`, `!shell`
commands and `?` help keep working. It needs Jupyter's kernel package;
`pip install "slaython[jupyter]"` installs it with Slaython.

## Moving a Python project over

Plain Python is valid Slaython, so you can rename a `.py` file to `.slay`
and it still runs. Then switch it to slang at your own pace:

- `slaython slayify app.py -o app.slay` writes a slang version of a Python
  file, and warns about names that clash with Slaython words.
- `slaython glowup` swaps the Python keywords left in your `.slay` files
  for slang.
- `slaython build` turns Slaython back into plain Python that runs without
  Slaython installed.

See [Tools](tools.md) for each of these.
