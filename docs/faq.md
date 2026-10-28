# FAQ and limits

Answers to common questions, and the places where Slaython behaves in a way
you might not expect.

## Which Python versions work?

Python 3.10 and newer. Slaython uses only the standard library, so there is
nothing else to install. Slang works everywhere in your code on every
supported version, including inside f-string braces:

```slay
blueprint Bestie:
    cook __init__(mee, name):
        mee.name = name

    cook hi(mee):
        serve f"hi {mee.name}, {'ate' fr howlongisit(mee.name) > 2 ornah 'mid'}"

yap(Bestie("mia").hi())
```

## Can I use `cap` or `drop` as a variable name?

No. Slang words are reserved, the same way you can't name a Python variable
`if`. A variable called `cap` turns into `False`, and one called `drop`
turns into `yield`. The [keyword reference](keywords.md) lists every word.

There are exceptions, so Python libraries keep working:

- **Attributes are never translated.** `df.drop(...)` and `obj.cap` stay
  as they are.
- **Keyword arguments are never translated.** `reset_index(drop=nocap)`
  passes an argument called `drop`.
- **Soft words only count in their spot.** `spill`, `pov` and `runitfoo`
  only count at the start of a line ending in `:`. `lore`, `gang`,
  `speedrun`, `vibecheck`, `maincharacter` and `idc` only count at the start
  of a line. Elsewhere they are normal names.
- **Helpers only count when called.** `bedrot`, `pickone`, `squad` and the
  other helpers only count when you call them or use them as a decorator.

One case does break: importing a name that is a slang word, such as
`outta mylib pullup drop`. Pull up the module and write `mylib.drop(...)`.

When you convert Python with `slaython slayify`, it warns you about names
that clash with Slaython words.

## Why did `slaython translate` drop my comments?

Most translation is word for word, so comments, blank lines and line
numbers stay exactly where they were. Files that use `shoot n:` or `|>` are
different: Slaython rebuilds the Python for those from the syntax tree,
and the syntax tree has no comments or blank lines. So `slaython translate`
prints those files without them.

This only affects the printed Python. Running the file, error messages and
line numbers in tracebacks are not affected.

## My code froze the playground. What now?

The playground runs your code in the browser tab itself. An infinite loop,
such as `lockedin nocap:` with no `dip`, keeps the tab busy forever, and
the page stops responding. There is no stop button.

Close the tab, or reload the page. The playground saves your code in the
browser a moment after you type, so a reload brings it back. Code you
opened from a link and haven't changed is still in that link.

## Can I mix Python keywords and slang?

Yes. Every Python keyword still works, so `if x: return True` is valid
Slaython. Use `slaython glowup` when you want to switch the rest to slang.

## Does Slaython make my code slower?

No. Slaython translates your code once, when it loads, and from then on it
is normal Python running at normal speed. The only extra work is the
translation itself, which happens each time a `.slay` file is loaded:
Slaython doesn't save `.pyc` files for `.slay` files.

## Are line numbers in errors right?

Yes. Translation never adds or removes lines, so line 12 of your `.slay`
file is line 12 of the Python, and the error carets point at the right
columns of your Slaython code.

## What happens if `foo.py` and `foo.slay` are in the same folder?

`pullup foo` loads `foo.py`. Python's own files win.

## How do I turn off the slang notes under errors?

Run `slaython --no-vibes app.slay`, or set the environment variable
`SLAYTHON_VIBES=0`.

## Can I add my own words?

Yes, per project. Add a `[tool.slaython.words]` table to your
`pyproject.toml`. See [project words](guide.md#project-words).

## How do I suggest a new word or report a bug?

Open an issue on [GitHub](https://github.com/memoliertorerr/Slaython/issues).
There are templates for bugs, new slang and features. The word list lives in
[`slaython/keywords.py`](https://github.com/memoliertorerr/Slaython/blob/main/slaython/keywords.py),
and this site's pages live in
[`docs/`](https://github.com/memoliertorerr/Slaython/tree/main/docs).
