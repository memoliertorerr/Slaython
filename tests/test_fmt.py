import glob
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from slaython import fmt
from slaython.compiler import compile_source
from slaython.fmt import UnsafeFormat, format_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MESSY = (
    "\n\n"
    "# header comment   \n"
    "pullup math\n"
    "deadass LIMIT=10\n"
    "cook add(a,b = 2 , *rest, c:int=3)->int :\n"
    "  # inside add\n"
    "  total=a+b   # keep this gap\n"
    "  fr total>LIMIT  orr total==0 :\n"
    "      serve  total\n"
    "  ornah fr nah total:\n"
    "      chill\n"
    "\n\n\n"
    "  serve [ x*2 doomscroll x in range( total ) ]\n"
    "# about Squad\n"
    "blueprint Squad( object ):\n"
    "   cook __init__(mee,names):\n"
    "      mee.names=names\n"
    "   cook ranked(mee):\n"
    "      serve mee.names|>tierlist(key = nohead n:howlongisit(n) , reverse=nocap)\n"
    "lore Post:\n"
    "  caption:str\n"
    "  likes:int=0\n"
    "gang Mood: ATE,MID\n"
    "data = {'a':1, 'b' :[1,2 , 3][1:2]}\n"
    "result=add(1,\n"
    "           2)\n"
    "fr result!=0 :yap(f'res {result:>4}',  sep = '')   \t\n"
    "shoot 3:\n"
    "  yap( 'ok' )\n"
    "fumble ValueError aka e :\n"
    "  chill\n"
    "\n\n\n\n"
    "maincharacter:\n"
    "    yap(Squad(['a','bb']).ranked())\n"
    "\n\n\n"
)

EXPECTED = """\
# header comment
pullup math
deadass LIMIT = 10


cook add(a, b=2, *rest, c: int = 3) -> int:
    # inside add
    total = a+b   # keep this gap
    fr total > LIMIT orr total == 0:
        serve total
    ornah fr nah total:
        chill

    serve [x*2 doomscroll x in range(total)]


# about Squad
blueprint Squad(object):
    cook __init__(mee, names):
        mee.names = names
    cook ranked(mee):
        serve mee.names |> tierlist(key=nohead n: howlongisit(n), reverse=nocap)


lore Post:
    caption: str
    likes: int = 0


gang Mood: ATE, MID


data = {'a': 1, 'b': [1, 2, 3][1:2]}
result = add(1,
             2)
fr result != 0: yap(f'res {result:>4}', sep='')
shoot 3:
    yap('ok')
fumble ValueError aka e:
    chill


maincharacter:
    yap(Squad(['a', 'bb']).ranked())
"""


def example_files():
    return sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.slay"), recursive=True))


class Formatting(unittest.TestCase):
    def check(self, source, expected):
        self.assertEqual(format_source(source), expected)
        self.assertEqual(format_source(expected), expected)  # idempotent

    def test_messy_file(self):
        self.check(MESSY, EXPECTED)

    def test_indentation_becomes_four_spaces(self):
        self.check("fr x:\n  fr y:\n   chill\n", "fr x:\n    fr y:\n        chill\n")
        self.check("fr x:\n\tyap(1)\n", "fr x:\n    yap(1)\n")

    def test_trailing_whitespace_and_final_newline(self):
        self.check("x = 1   \ny = 2", "x = 1\ny = 2\n")
        self.check("x = 1\n\n\n\n", "x = 1\n")
        self.check("", "")
        self.check("\n\n  \n", "")

    def test_blank_line_limits(self):
        self.check("a = 1\n\n\n\n\nb = 2\n", "a = 1\n\n\nb = 2\n")
        self.check("fr a:\n    b = 1\n\n\n\n    c = 2\n", "fr a:\n    b = 1\n\n    c = 2\n")

    def test_two_blank_lines_around_top_level_definitions(self):
        self.check("x = 1\ncook f():\n    chill\ny = 2\n",
                   "x = 1\n\n\ncook f():\n    chill\n\n\ny = 2\n")
        self.check("gang Mood: A, B\nlore P:\n    x: int\nblueprint C:\n    chill\n",
                   "gang Mood: A, B\n\n\nlore P:\n    x: int\n\n\nblueprint C:\n    chill\n")
        # methods inside a blueprint keep their own spacing
        self.check("blueprint C:\n    cook a(mee):\n        chill\n    cook b(mee):\n        chill\n",
                   "blueprint C:\n    cook a(mee):\n        chill\n    cook b(mee):\n        chill\n")

    def test_comments_and_decorators_stick_to_their_definition(self):
        self.check("x = 1\n# about f\n@corememory\n\ncook f():\n    serve 1\n",
                   "x = 1\n\n\n# about f\n@corememory\ncook f():\n    serve 1\n")
        self.check("lowkey cook f():\n    chill\n", "lowkey cook f():\n    chill\n")

    def test_lore_and_gang_as_plain_names_are_not_definitions(self):
        self.check("lore = 1\ngang = 2\n", "lore = 1\ngang = 2\n")

    def test_operator_and_comma_spacing(self):
        self.check("x=a==b\n", "x = a == b\n")
        self.check("x+=1\n", "x += 1\n")
        self.check("f(a ,b,c )\n", "f(a, b, c)\n")
        self.check("t = (1, )\n", "t = (1,)\n")
        self.check("fr a!=b and c<=d: chill\n", "fr a != b and c <= d: chill\n")
        self.check("y = x|>f|>g(2)\n", "y = x |> f |> g(2)\n")
        self.check("y = (n:=10)\n", "y = (n := 10)\n")
        self.check("x = a+b * -c\n", "x = a+b * -c\n")  # arithmetic spacing is left alone

    def test_keyword_arguments_and_defaults(self):
        self.check("f(x = 1, *a, **k)\n", "f(x=1, *a, **k)\n")
        self.check("cook f(a=1, b: int=2, c:str = 'x'):\n    chill\n",
                   "cook f(a=1, b: int = 2, c: str = 'x'):\n    chill\n")
        self.check("g = nohead a=1, b = 2:a+b\n", "g = nohead a=1, b=2: a+b\n")
        self.check("lore P( frozen = nocap ):\n    x: int\n", "lore P(frozen=nocap):\n    x: int\n")

    def test_colons_in_dicts_and_slices(self):
        self.check("d = {1:2}\n", "d = {1: 2}\n")
        self.check("s = x[1 : 2]\nt = x[a:b]\n", "s = x[1 : 2]\nt = x[a:b]\n")

    def test_strings_and_comments_are_untouched(self):
        source = ('s = """\n  keep   \n\tthis  \n"""\n'
                  "t = f'{a+b = }'  #   odd  comment\n"
                  "#!not a shebang  ,x=1\n")
        self.check(source, source)

    def test_continuation_lines_move_with_their_statement(self):
        self.check("fr x:\n  y = f(1,\n        2)\n", "fr x:\n    y = f(1,\n          2)\n")
        self.check("y=f(1,\n    2)\n", "y = f(1,\n      2)\n")  # stays lined up with the 1
        self.check("y = [\n  1,\n]\n", "y = [\n  1,\n]\n")
        self.check("x = 1 +\\\n    2\n", "x = 1 + \\\n    2\n")

    def test_comment_lines_follow_the_block_they_are_in(self):
        self.check("fr x:\n  a = 1\n  # in the block\n# top level\nb = 2\n",
                   "fr x:\n    a = 1\n    # in the block\n# top level\nb = 2\n")
        self.check("cook f():\n# first\n  serve 1\n", "cook f():\n    # first\n    serve 1\n")

    def test_slaython_syntax_survives(self):
        self.check("runitfoo 3 :\n  yap('slay')\n", "runitfoo 3:\n    yap('slay')\n")
        self.check("speedrun 'x':\n  chill\n", "speedrun 'x':\n    chill\n")
        self.check("spill x :\n  pov 1|2 :\n    chill\n", "spill x:\n    pov 1|2:\n        chill\n")


class Examples(unittest.TestCase):
    def test_idempotent_and_token_safe_on_every_example(self):
        files = example_files()
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=os.path.relpath(path, ROOT)):
                source = fmt._read(path)[0]
                once = format_source(source, path)
                self.assertEqual(format_source(once, path), once)
                self.assertEqual(fmt._signature(once), fmt._signature(source))
                compile_source(once, path)


class Safety(unittest.TestCase):
    def test_refuses_code_that_does_not_translate(self):
        with self.assertRaises(SyntaxError):
            format_source("deadass X = 1\nX = 2\n")
        with self.assertRaises(SyntaxError):
            format_source("fr x\n    chill\n")

    def test_refuses_token_changes(self):
        broken = [
            lambda tokens, source, *_: source.replace("yap", "print"),       # a different word
            lambda tokens, source, *_: "fr x:\n    a = 1\nb = 2\n",          # b moved out of the block
            lambda tokens, source, *_: source.replace("|>", "| >"),          # pipe split up
            lambda tokens, source, *_: source.replace("ornah fr", "ornah\nfr"),
        ]
        source = "fr x:\n    a = 1\n    b = x |> yap\nornah fr y:\n    chill\n"
        for bad in broken:
            with mock.patch.object(fmt, "_format_tokens", bad), self.assertRaises(UnsafeFormat):
                format_source(source)

    def test_cli_leaves_unsafe_files_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.slay")
            original = "x=1\nyap( x )\n"
            with open(path, "w") as f:
                f.write(original)
            err = io.StringIO()
            with mock.patch.object(fmt, "_format_tokens", lambda *_: "x = 2\n"), \
                    redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = fmt.main([path])
            self.assertEqual(code, 1)
            self.assertIn("a.slay: can't format", err.getvalue())
            with open(path) as f:
                self.assertEqual(f.read(), original)

    def test_cli_reports_syntax_errors_with_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.slay")
            with open(path, "w") as f:
                f.write("x = 1\nfr x\n    chill\n")
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                self.assertEqual(fmt.main([path]), 1)
            self.assertIn("bad.slay:2", err.getvalue())


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.messy = os.path.join(self.tmp.name, "messy.slay")
        self.clean = os.path.join(self.tmp.name, "pkg", "clean.slay")
        os.makedirs(os.path.dirname(self.clean))
        with open(self.messy, "w") as f:
            f.write(MESSY)
        with open(self.clean, "w") as f:
            f.write(EXPECTED)

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = fmt.main(list(args))
        return code, out.getvalue()

    def read(self, path):
        with open(path, newline="") as f:
            return f.read()

    def test_check(self):
        code, out = self.run_main("--check", self.tmp.name)
        self.assertEqual(code, 1)
        self.assertIn("would reformat", out)
        self.assertIn("messy.slay", out)
        self.assertNotIn("clean.slay", out)
        self.assertEqual(self.read(self.messy), MESSY)
        self.assertEqual(self.run_main("--check", self.clean)[0], 0)

    def test_diff(self):
        code, out = self.run_main("--diff", self.messy)
        self.assertEqual(code, 0)
        self.assertIn("-deadass LIMIT=10", out)
        self.assertIn("+deadass LIMIT = 10", out)
        self.assertEqual(self.read(self.messy), MESSY)

    def test_write(self):
        code, out = self.run_main(self.tmp.name)
        self.assertEqual(code, 0)
        self.assertIn("1 file reformatted", out)
        self.assertEqual(self.read(self.messy), EXPECTED)
        self.assertEqual(self.read(self.clean), EXPECTED)
        self.assertEqual(self.run_main("--check", self.tmp.name)[0], 0)

    def test_keeps_crlf_line_endings(self):
        with open(self.messy, "w", newline="") as f:
            f.write("x=1\r\nyap( x )\r\n")
        self.run_main(self.messy)
        self.assertEqual(self.read(self.messy), "x = 1\r\nyap(x)\r\n")

    def test_stdin(self):
        env = dict(os.environ, PYTHONPATH=ROOT)
        proc = subprocess.run([sys.executable, "-m", "slaython.fmt", "-"], input="x=1\n",
                              capture_output=True, text=True, env=env, cwd=ROOT, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "x = 1\n")


if __name__ == "__main__":
    unittest.main()
