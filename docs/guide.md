# Language guide

Slaython is Python with different words. If you know Python, you already
know how Slaython works: same indentation, same operators, same standard
library. This page shows each part of the language with examples. The
[keyword reference](keywords.md) has the full word list.

Plain Python keywords keep working, so `if` and `fr` both mean `if`. You
can mix them, or move a Python file over one word at a time.

## Values and logic

| Slaython | Python |
|---|---|
| `nocap` | `True` |
| `cap` | `False` |
| `ghosted` | `None` |
| `orr` | `or` |
| `nah` | `not` |
| `literally` | `is` |
| `and`, `in` | stay the same |

```slay
online = nocap
muted = cap
bio = ghosted

fr online and nah muted:
    yap("they're here")

fr bio literally ghosted orr bio == "":
    yap("no bio, very mysterious")

yap("ate" in ["ate", "mid"])
```

`literally` is identity, like `is`: use it for `ghosted`, `nocap` and
`cap`. Use `==` to compare values.

## Control flow

### fr, ornah fr, ornah

`fr` is `if`, `ornah fr` is `elif` and `ornah` is `else`.

```slay
likes = 420

fr likes > 1000:
    yap("viral")
ornah fr likes > 100:
    yap("doing numbers")
ornah:
    yap("mid")

vibe = "W" fr likes > 100 ornah "L"   # the one-line form works too
yap(vibe)
```

### doomscroll

`doomscroll` is `for`. It goes through a list, a string, a range or any
other iterable.

```slay
squad = ["mia", "kai", "jo"]

doomscroll name in squad:
    yap("hey", name)

doomscroll i, name in enumerate(squad, 1):
    yap(i, name)

lengths = [howlongisit(n) doomscroll n in squad]   # comprehensions too
yap(lengths)
```

### lockedin, dip, anyways, chill

`lockedin` is `while`. `dip` is `break`, `anyways` is `continue` and
`chill` is `pass`.

```slay
n = 0
lockedin nocap:
    n += 1
    fr n % 2 == 0:
        anyways        # skip even numbers
    fr n > 7:
        dip            # leave the loop
    yap(n)

fr n > 100:
    chill              # nothing to do here yet
```

To repeat a block a fixed number of times, use [`runitfoo`](#runitfoo).

## Functions

`cook` is `def` and `serve` is `return`. Defaults, keyword arguments,
`*args`, `**kwargs`, type hints and decorators all work as in Python.

```slay
cook greet(name, hype=1):
    serve "hey " + name + "!" * hype

yap(greet("mia"))
yap(greet("kai", hype=3))

cook total(*nums):
    serve sum(nums)

yap(total(1, 2, 3))
```

### nohead

`nohead` is `lambda`: a small function with no name.

```slay
double = nohead x: x * 2
yap(double(21))

posts = [("fit check", 420), ("mid take", 12)]
yap(tierlist(posts, key=nohead p: p[1]))
```

### drop

`drop` is `yield`. A function that drops values is a generator: it hands
out one value at a time.

```slay
cook feed():
    n = 0
    lockedin nocap:
        n += 1
        drop "post #" + str(n)

doomscroll post in feed():
    yap(post)
    fr post == "post #3":
        dip
```

`drop outta` is `yield from`.

### corememory

`@corememory` is `@functools.cache`. The function remembers its answers,
so the next call with the same arguments returns right away.

```slay
@corememory
cook fib(n):
    fr n < 2:
        serve n
    serve fib(n - 1) + fib(n - 2)

yap(fib(80))
```

## Blueprints

`blueprint` is `class`, `mee` is `self` and `og()` is `super()`.

```slay
blueprint Creator:
    cook __init__(mee, name, followers=0):
        mee.name = name
        mee.followers = followers

    cook vibe(mee):
        fr mee.followers > 10_000:
            serve "lowkey famous"
        serve "npc era"


blueprint Streamer(Creator):
    cook __init__(mee, name, followers, game):
        og().__init__(name, followers)
        mee.game = game

    cook vibe(mee):
        serve og().vibe() + ", streams " + mee.game


doomscroll c in [Creator("mia", 40_000), Streamer("kai", 900, "minecraft")]:
    yap(c.name, "->", c.vibe())
```

Special methods (`__init__`, `__repr__`, `__eq__`, ...) keep their Python
names. `giving(x, Creator)` is `isinstance(x, Creator)`.

For classes that only hold data, use [`lore`](#lore). For a fixed set of
named values, use [`gang`](#gang).

## Errors

`shoot` is `try`, `fumble` is `except`, `periodt` is `finally` and `yeet`
is `raise`. `aka` is `as`, and `skillissue` is `Exception`.

```slay
blueprint RatioError(skillissue):
    chill


cook post(likes, replies):
    fr replies > likes:
        yeet RatioError("got ratioed")
    serve "W post"


doomscroll likes, replies in [(100, 3), (5, 80)]:
    shoot:
        yap(post(likes, replies))
    fumble RatioError aka e:
        yap("L:", e)
    periodt:
        yap("next post...")
```

`ongod` is `assert`. It stops the program if the check is false:

```slay
score = 10
ongod score >= 0, "score can't be negative, that's cap"
yap("ongod check passed")
```

Slaython adds three things on top of this:

- [`yeet "message"`](#yeet-message) raises an error from a plain string.
- [`shoot n:`](#shoot-n-retries) retries a block before giving up.
- [`idc`](#idc) runs a block and ignores one kind of error.

## Modules

`pullup` is `import`, `outta` is `from` and `aka` is `as`.

```slay
pullup math
pullup random aka rng
outta collections pullup Counter

yap(math.sqrt(16))
yap(rng.randint(1, 6) in range(1, 7))
yap(Counter("slay slay").most_common(1))
```

Any Python module or package works, including ones you installed with
pip. A `.slay` file can also `pullup` another `.slay` file in the same
folder. See [Working with Python](python.md) for both directions.

To run code only when a file is run directly, not when it is pulled up,
use [`maincharacter`](#maincharacter).

## Scope and resources

`linkup` is `with`. It opens a resource and closes it when the block ends.

```slay norun
linkup open("notes.txt") aka f:
    yap(f.read())
```

`cancel` is `del`. It removes a name, a list item or a dict key.

```slay
feed = ["fit check", "mid take", "ratio"]
cancel feed[1]
yap(feed)

likes = {"mia": 3, "kai": 5}
cancel likes["kai"]
yap(likes)
```

`viral` is `global` and `mutuals` is `nonlocal`. They let a function change
a name from outside it.

```slay
views = 0

cook watch():
    viral views
    views += 1

watch()
watch()
yap(views)

cook counter():
    count = 0
    cook bump():
        mutuals count
        count += 1
        serve count
    serve bump

tap = counter()
tap()
yap(tap())
```

## Async

`lowkey` is `async`, `holdup` is `await`, and `squad(...)` is
`asyncio.gather(...)`: it runs several tasks together and waits for all of
them.

```slay
pullup asyncio


lowkey cook fetch_vibe(user, delay):
    holdup asyncio.sleep(delay)
    serve user + " ate"


lowkey cook main():
    results = holdup squad(
        fetch_vibe("ava", 0.02),
        fetch_vibe("leon", 0.01),
    )
    yap(results)


asyncio.run(main())
```

`lowkey doomscroll` and `lowkey linkup` are `async for` and `async with`.

## Pattern matching

`spill` is `match` and `pov` is `case`. Patterns work exactly as in Python:
literals, lists, dicts, classes, `|` alternatives and `fr` guards.

```slay
cook react(event):
    spill event:
        pov {"type": "like", "user": user}:
            serve user + " liked your post"
        pov {"type": "comment", "text": text} fr howlongisit(text) > 20:
            serve "long comment, read it later"
        pov {"type": "comment", "text": text}:
            serve "comment: " + text
        pov [first, *rest]:
            serve str(howlongisit(rest) + 1) + " events"
        pov _:
            serve "no idea"


yap(react({"type": "like", "user": "mia"}))
yap(react({"type": "comment", "text": "ate"}))
yap(react(["a", "b", "c"]))
yap(react(42))
```

`spill` and `pov` are soft keywords, like `match` and `case` in Python:
they only count at the start of a line that ends in `:`. Anywhere else they
are normal names, so `spill = "tea"` works.

## Builtins and helpers

These names stand for Python builtins:

| Slaython | Python | |
|---|---|---|
| `yap()` | `print()` | print to the console |
| `hmu()` | `input()` | ask the user for a line of text |
| `howlongisit()` | `len()` | how many items |
| `goat()` | `max()` | the biggest |
| `flop()` | `min()` | the smallest |
| `tierlist()` | `sorted()` | a sorted copy |
| `whoisyou()` | `type()` | the type of a value |
| `giving()` | `isinstance()` | `giving(x, int)` |
| `og()` | `super()` | the parent class |
| `touchgrass()` | `exit()` | quit the program |
| `bruh()` | `breakpoint()` | stop and open the debugger |
| `skillissue` | `Exception` | the base error type |
| `mee` | `self` | the object itself |

```slay
scores = [7, 42, 3]
yap(howlongisit(scores), goat(scores), flop(scores))
yap(tierlist(scores, reverse=nocap))
yap(whoisyou(scores).__name__, giving(scores, list))
```

Every other Python builtin (`range`, `sum`, `str`, `open`, ...) keeps its
name.

Slaython also comes with a few helpers:

| Helper | What it does |
|---|---|
| `lowkeysus(x)` | prints the expression and its value, returns the value ([more](#lowkeysus)) |
| `bedrot(s)` | sleeps for `s` seconds (`time.sleep`) |
| `headzortailz()` | flips a coin: `nocap` or `cap` |
| `pickone(items)` | a random item (`random.choice`) |
| `@corememory` | remembers a function's answers (`functools.cache`) |
| `squad(a, b)` | runs async tasks together (`asyncio.gather`) |

```slay
yap(pickone(["ate", "slay", "mid"]))
fr headzortailz():
    yap("heads")
ornah:
    yap("tails")
bedrot(0.1)
yap("ok, back")
```

Helpers only count when you call them or use them as a decorator. A
variable called `squad` stays a normal variable.

## Slaython-only syntax

These features don't exist in Python. Slaython turns them into normal
Python when it translates your code.

### runitfoo

`runitfoo n:` runs a block `n` times. It is `for _ in range(n):`.

```slay
runitfoo 3:
    yap("slay")

laps = 2
runitfoo laps * 2:
    yap("lap")
```

### deadass

`deadass` makes a constant. Assigning the name again anywhere in the same
file is a syntax error, and so are `+=` and `cancel`.

```slay
deadass MAX_LIKES = 1_000
deadass APP_NAME: str = "feed"   # type hints work

yap(APP_NAME, MAX_LIKES)
```

```slay-fragment
deadass MAX_LIKES = 1_000
MAX_LIKES = 2_000    # SyntaxError: MAX_LIKES is deadass (a constant)
```

The check happens when the file is translated, before anything runs. Other
modules that import the name can still change it at run time, like any
Python name.

### yeet "message" {#yeet-message}

`yeet` with a plain string raises an `Exception` with that message. It
saves you from writing a class for a one-off error.

```slay
cook set_likes(n):
    fr n < 0:
        yeet "likes can't be negative"
    serve n

shoot:
    set_likes(-5)
fumble skillissue aka e:
    yap("L:", e)
```

f-strings work too (`yeet f"bad value: {n}"`). `yeet "message" outta err`
keeps the original error as the cause, like `raise ... from err`.

### lowkeysus

`lowkeysus(x)` is a debug print. It prints the line number, the expression
as you wrote it, and its value, then returns the value. You can wrap it
around any expression without changing what the code does.

```slay
likes = [420, 12, 77]
total = lowkeysus(sum(likes) * 2)
yap(total)
```

That prints `lowkeysus line 2: sum(likes) * 2 = 1018` to stderr, then
`1018`.

### maincharacter

`maincharacter:` is `if __name__ == "__main__":`. The block only runs when
the file is run directly, not when another file pulls it up.

```slay
cook main():
    yap("running as the main character")

maincharacter:
    main()
```

### lore

`lore` makes a data class: a blueprint that holds data. You list the
fields, and Slaython writes `__init__`, `__repr__` and `==` for you.

```slay
lore Post:
    caption: str
    likes: int = 0

    cook ratio(mee, replies):
        serve replies / goat(mee.likes, 1)


p = Post("fit check", 420)
yap(p)
yap(p == Post("fit check", 420))
yap(p.ratio(42))
```

Options for Python's `dataclass` go in the header, and a `lore` can extend
another `lore`:

```slay
lore Point(frozen=nocap):
    x: int
    y: int = 0

lore Point3(Point, frozen=nocap):
    z: int = 0

yap(Point3(1, 2, 3))
```

A `lore` is a real dataclass, so `dataclasses.field`, `asdict` and the rest
work. Use `field(default_factory=list)` for a list default. `slots=nocap` is
not supported.

### gang

`gang` makes an enum: a fixed set of named values. Members are numbered
for you, starting at 1.

```slay
gang Mood: ATE, MID, COOKED

gang Size:
    SMALL
    BIG, HUGE

    cook is_big(mee):
        serve mee != Size.SMALL


yap(Mood.ATE, Mood.ATE.value)
yap([m.name doomscroll m in Mood])
yap(Size.HUGE.is_big())
```

A line with names only gets numbers. To pick the values yourself, write
them out, as in a Python enum:

```slay
gang Color:
    RED = "red"
    LIME = "lime"

yap(Color("lime"))
```

### shoot n: retries {#shoot-n-retries}

`shoot n:` is a `shoot` (try) that runs its block up to `n` times. If the
block fails every time, the `fumble` runs as usual.

```slay
attempts = 0

cook load_feed():
    viral attempts
    attempts += 1
    fr attempts < 3:
        yeet ConnectionError("wifi is lagging")
    serve ["fit check", "ratio"]

shoot 5:
    feed = load_feed()
fumble ConnectionError:
    feed = []

yap(feed, "after", attempts, "tries")
```

- Only errors that the `fumble` catches are retried. With no `fumble`,
  any error is retried, and the last one is raised.
- `periodt` runs once at the end, not after every try.
- `dip` and `anyways` can't go straight inside a `shoot n:` block. Put the
  `shoot n:` inside the loop body instead.
- `n` can be any expression, but keep `shoot n:` on one line.

### speedrun

`speedrun:` times a block and prints how long it took to stderr. Give it a
label to tell timers apart.

```slay
speedrun:
    total = sum(range(1_000_000))

speedrun "ranking":
    ranked = tierlist(range(100_000), reverse=nocap)

yap(total, ranked[0])
```

That prints lines like `speedrun line 1: 0.012s` and
`speedrun ranking: 0.004s`.

### Pipes: |> {#pipes}

`x |> f` is `f(x)`, and `x |> f(y)` is `f(x, y)`: the value goes in as the
first argument. Pipes read left to right, so a chain of steps reads in the
order it runs.

```slay
posts = [("fit check", 420), ("ratio", 12), ("mid take", 77)]

top = posts |> tierlist(key=nohead p: p[1], reverse=nocap)
yap(top)

yap(posts |> howlongisit)
yap([p[0] doomscroll p in posts] |> ", ".join)
yap("  slay  " |> str.strip |> str.upper)
```

`|>` binds like Python's `|`: tighter than comparisons, `and` and `orr`,
looser than `+` and `*`. So `a |> f == b` is `f(a) == b`, and
`x * 2 |> str` is `str(x * 2)`.

### vibecheck

`vibecheck "name":` is a test that lives next to your code. Running the file
skips it. [`slaython test`](tools.md#slaython-test) runs it.

```slay
cook double(n):
    serve n * 2

vibecheck "double works":
    ongod double(2) == 4
    ongod double(-1) == -2

yap(double(21))
```

### idc

`idc SomeError:` runs a block and ignores that error. `idc:` on its own
ignores any error. It is `with contextlib.suppress(...)`.

```slay
idc ValueError:
    likes = int("a lot")
    yap("never printed")

idc KeyError, IndexError:
    yap([][0])

yap("still here")
```

The block stops at the error, so lines after it in the block don't run.

### Where these words count

`lore`, `gang`, `speedrun`, `vibecheck`, `maincharacter` and `idc` only
count at the start of a line. `runitfoo`, `spill` and `pov` also need the
line to end in `:`. Everywhere else they are normal names.

## Project words

A project can add its own words in its `pyproject.toml`. Each new word
stands for a Python keyword or builtin, or for a Slaython word:

```toml
[tool.slaython.words]
frfr = "if"          # a Python keyword or builtin...
vibe = "doomscroll"  # ...or an existing Slaython word
spit = "print"
```

Every `.slay` file under the folder with that `pyproject.toml` can then use
them next to the built-in words:

```slay-fragment
vibe n in range(3):
    frfr n > 0:
        spit(n)
```

The REPL and `slaython -c` use the `pyproject.toml` of the current folder
(or the closest parent folder). A new word has to be a valid name, and it
can't be a Python keyword or a word Slaython already has, so the built-in
words read the same in every project.
