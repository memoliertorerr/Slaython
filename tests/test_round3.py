import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

import slaython
from slaython import transpile
from slaython.dialect import _simple_table, load_words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(src, ns=None):
    ns = {} if ns is None else ns
    slaython.slay(textwrap.dedent(src), ns)
    return ns


class Idc(unittest.TestCase):
    def test_ignores_listed_errors(self):
        ns = run("""\
            x = 1
            idc KeyError, ValueError:
                x = {}["nope"]
            """)
        self.assertEqual(ns["x"], 1)

    def test_bare_idc_ignores_everything_but_other_errors_pass(self):
        run("idc:\n    1 / 0\n")
        with self.assertRaises(ZeroDivisionError):
            run("idc KeyError:\n    1 / 0\n")

    def test_plain_name(self):
        self.assertEqual(transpile("idc = 3\nyap(idc)"), "idc = 3\nprint(idc)")


class Helpers(unittest.TestCase):
    def test_bruh_is_breakpoint(self):
        self.assertEqual(transpile("bruh()"), "breakpoint()")

    def test_corememory_caches(self):
        ns = run("""\
            calls = []
            @corememory
            cook slow(n):
                calls.append(n)
                serve n * 2
            out = [slow(2), slow(2), slow(3)]
            """)
        self.assertEqual((ns["out"], ns["calls"]), ([4, 4, 6], [2, 3]))

    def test_squad_gathers(self):
        ns = run("""\
            pullup asyncio
            lowkey cook two(x):
                holdup asyncio.sleep(0)
                serve x * 2
            lowkey cook main():
                serve holdup squad(two(1), two(2), two(3))
            out = asyncio.run(main())
            """)
        self.assertEqual(ns["out"], [2, 4, 6])

    def test_helpers_only_count_when_called(self):
        ns = run("squad = [3, 1]\nout = tierlist(squad)\n")
        self.assertEqual(ns["out"], [1, 3])


class ProjectWords(unittest.TestCase):
    def make_project(self, words, code):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "pyproject.toml"), "w") as f:
            f.write('[project]\nname = "demo"\n\n[tool.slaython.words]\n' + words)
        os.mkdir(os.path.join(d, "src"))
        path = os.path.join(d, "src", "app.slay")
        with open(path, "w") as f:
            f.write(textwrap.dedent(code))
        return d, path

    def run_file(self, path, cwd=None):
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-m", "slaython", path], capture_output=True,
                              text=True, env=env, cwd=cwd or ROOT, timeout=60)

    def test_aliases_of_every_kind(self):
        _, path = self.make_project(
            'frfr = "if"\nvibe = "doomscroll"\norfr = "elif"\nspit = "print"\ndatapls = "lore"\n',
            """\
            datapls P:
                x: int
            vibe i in range(3):
                frfr i == 0:
                    spit("zero", P(1))
                orfr i == 1:
                    yap("one")
                ornah:
                    spit("two")
            """)
        r = self.run_file(path)
        self.assertEqual(r.stdout, "zero P(x=1)\none\ntwo\n", r.stderr)

    def test_defaults_still_work_and_attributes_untouched(self):
        d, path = self.make_project('spit = "print"\n', "fr nocap:\n    spit(str.upper('x'))\n")
        self.assertEqual(self.run_file(path).stdout, "X\n")
        words = load_words(os.path.join(d, "pyproject.toml"))
        self.assertEqual(slaython.transpiler.translate("obj.spit = spit", "x.slay", words).python,
                         "obj.spit = print")

    def test_bad_words_are_refused(self):
        for bad in ('fr = "if"\n', 'class = "if"\n', 'zzz = "nonsense"\n', '"two words" = "if"\n'):
            with self.subTest(bad=bad):
                _, path = self.make_project(bad, "yap(1)\n")
                r = self.run_file(path)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("tool.slaython.words", r.stderr)

    def test_snippets_use_the_working_directory(self):
        d, _ = self.make_project('spit = "print"\n', "chill\n")
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-m", "slaython", "-c", "spit('hi')"], capture_output=True,
                           text=True, env=env, cwd=d, timeout=60)
        self.assertEqual(r.stdout, "hi\n", r.stderr)

    def test_fallback_reader_for_python_310(self):
        text = '[tool.other]\na = "b"\n\n[tool.slaython.words]\nfrfr = "if"  # comment\nspit = "print"\n[x]\nc = "d"\n'
        self.assertEqual(_simple_table(text, "tool.slaython.words"), {"frfr": "if", "spit": "print"})


if __name__ == "__main__":
    unittest.main()
