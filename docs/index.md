# Slaython

Slaython is Python with gen-z slang keywords. `fr` is `if`, `doomscroll` is
`for`, `cook` is `def` and `yap` is `print`. It runs on the normal Python
interpreter, so every Python library works in it. Python can import
Slaython files, and Slaython can import Python files.

```slay
cook rate(fit):
    fr fit == "ate":
        serve "no cap, that ate"
    ornah fr fit literally ghosted:
        serve "got ghosted"
    ornah:
        serve "lowkey mid rn"

doomscroll fit in ["ate", ghosted, "mid"]:
    yap(rate(fit))
```

Press **Run in playground** on any example to open it in the browser
playground. Nothing to install.

## Install

Slaython is on [PyPI](https://pypi.org/project/slaython/). It needs Python
3.10 or newer and nothing else:

```sh
pip install slaython
```

That gives you two commands, `slaython` and `slay`. They do the same thing.
`python -m slaython` works too.

Check that it works:

```sh
slaython -c 'yap("hi bestie")'
```

## How it works

Slaython translates your code to Python, word by word, and then Python runs
it. A few things follow from that:

- **Every Python library works.** `pullup numpy aka np` is `import numpy as np`.
- **Line numbers stay the same.** Line 12 of your `.slay` file is line 12
  of the Python, so tracebacks point at the right line.
- **Plain Python still works.** Python keywords are valid Slaython, so you
  can mix styles or move a file over bit by bit.
- **Errors come with a translation.** Tracebacks show your Slaython code,
  plus a short note in slang on what went wrong.

## Where to go next

- [Getting started](getting-started.md): your first program, running files,
  the REPL and the built-in tutorial.
- [Language guide](guide.md): everything the language can do, with examples.
- [Keyword reference](keywords.md): every word, the Python it stands for,
  and why.
- [Working with Python](python.md): importing in both directions, running
  Slaython inside Python, and Jupyter.
- [Tools](tools.md): tests, formatting, linting, translating, the VS Code
  extension and the full command list.
- [FAQ and limits](faq.md): things that can trip you up.

The source is on [GitHub](https://github.com/memoliertorerr/Slaython).
Slaython is MIT licensed.
