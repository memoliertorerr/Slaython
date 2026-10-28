# Getting started

This page takes you from install to your first program. If you haven't
installed Slaython yet, run `pip install slaython` (Python 3.10 or newer).

## Your first program

Slaython files end in `.slay`. Make a file called `hello.slay`:

```slay
yap("hello world, no cap")

name = "bestie"
fr howlongisit(name) > 3:
    yap("ayy", name, "welcome to Slaython")
ornah:
    yap("short name, still valid")
```

Run it:

```sh
slaython hello.slay
```

`yap` is `print`, `fr` is `if`, `ornah` is `else` and `howlongisit` is
`len`. Everything else is regular Python: strings, numbers, `==`, `+`,
indentation and so on.

## Running code

There are a few ways to run Slaython:

```sh
slaython hello.slay            # run a file
slaython hello.slay a b c      # run a file with arguments (sys.argv)
slay hello.slay                # same thing, shorter
python -m slaython hello.slay  # same thing, without the script on PATH
slaython run hello.slay        # same thing, spelled out
slaython -c 'yap(6 * 7)'       # run a snippet
cat hello.slay | slaython -    # run code piped in on stdin
```

Your program sees its arguments in `sys.argv`, like a Python script. The
folder of the file goes on `sys.path`, so it can `pullup` its neighbours.

### Reading input

`hmu()` is `input()`. It shows a prompt and returns what the user typed:

```slay
name = hmu("what do they call you? ") orr "bestie"
yap("ayy", name)
```

In the playground, `hmu()` opens a small browser prompt.

## When things go wrong

Errors show your Slaython line, not the translated Python. A short
explanation in slang follows:

```text
Traceback (most recent call last):
  File "oops.slay", line 2, in <module>
    yap(likes["mid"])
        ~~~~~^^^^^^^
KeyError: 'mid'
real talk: that key got ghosted. it's not in the dict
```

Syntax errors translate Python keywords back to slang, so you know which
word to fix:

```text
SyntaxError: expected 'except' or 'finally' block
real talk: syntax is not it. check your slang ('except' is 'fumble' in Slaython, 'finally' is 'periodt' in Slaython)
```

To turn the explanations off, run `slaython --no-vibes file.slay` or set
`SLAYTHON_VIBES=0`.

## The REPL

Run `slaython` with no file to get an interactive prompt:

```text
$ slaython
Slaython 0.3.1 on Python 3.12.4. no cap.
Type slang for the keyword sheet, exit() or Ctrl-D to dip.
slay> doomscroll n in range(3):
  ...     yap(n * 2)
  ...
0
2
4
slay> slang
```

- Type `slang` to print the keyword sheet.
- Blocks work like in the Python REPL: end them with an empty line.
- `exit()`, `touchgrass()` or Ctrl-D leaves.

## Learn the language: `slaython learn`

`slaython learn` is an interactive tutorial in your terminal. Each lesson
shows an example, then asks you to write a little code. Slaython runs your
answer and tells you if it's right.

```sh
slaython learn          # pick up where you left off
slaython learn 3        # jump to lesson 3
slaython learn --list   # every lesson, and which ones you finished
slaython learn --reset  # forget your progress and start over
```

While you're in a lesson, type your code and press Enter on an empty line
to run it. These commands also work at the prompt:

| Command | What it does |
|---|---|
| `hint` | a nudge in the right direction |
| `solution` | show one answer |
| `skip` | go to the next lesson |
| `back` | go to the previous lesson |
| `quit` | stop; your progress is saved |

Progress lives in `~/.slaython_learn.json`. Set `SLAYTHON_LEARN_FILE` to
keep it somewhere else.

## Try the playground

The [playground](../) runs Slaython in your browser. It loads the real
`slaython` package on Pyodide (Python compiled to WebAssembly), so it
behaves like your terminal. Press Run (Ctrl+Enter, or Cmd+Enter on a Mac),
switch to the Python tab to see the translation, or press Share to get a
link that carries your code.

## Next steps

- The [language guide](guide.md) walks through every feature.
- The [keyword reference](keywords.md) lists every word.
- The [VS Code extension](tools.md#vs-code) adds highlighting, hovers and a
  run button.
