import io
import os
import subprocess
import sys
import tempfile
import textwrap
import traceback
import unittest
from contextlib import redirect_stderr, redirect_stdout

import slaython
from slaython import transpile
from slaython.testing import run_tests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(src, ns=None):
    ns = {} if ns is None else ns
    slaython.slay(textwrap.dedent(src), ns)
    return ns


def run_cli(*args):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "slaython", *args], capture_output=True,
                          text=True, env=env, cwd=ROOT, timeout=60)


class MainCharacter(unittest.TestCase):
    def test_translates(self):
        self.assertEqual(transpile("maincharacter:\n    chill\n"), 'if __name__ == "__main__":\n    pass\n')

    def test_runs_only_as_main(self):
        self.assertEqual(run("x = 0\nmaincharacter:\n    x = 1\n", {"__name__": "__main__"})["x"], 1)
        self.assertEqual(run("x = 0\nmaincharacter:\n    x = 1\n", {"__name__": "lib"})["x"], 0)

    def test_slayify_and_plain_name(self):
        self.assertEqual(slaython.slayify("if __name__ == '__main__':\n    pass\n"), "maincharacter:\n    chill\n")
        self.assertEqual(transpile("maincharacter = 1"), "maincharacter = 1")


class Lore(unittest.TestCase):
    def test_dataclass(self):
        ns = run("""\
            lore Post:
                caption: str
                likes: int = 0
            p = Post("fit")
            """)
        self.assertEqual(repr(ns["p"]), "Post(caption='fit', likes=0)")
        self.assertEqual(ns["p"], ns["Post"]("fit", 0))

    def test_options_and_bases(self):
        ns = run("""\
            lore Point(frozen=nocap):
                x: int
            lore Point3(Point, frozen=nocap):
                z: int = 0
            p = Point3(1, 2)
            """)
        self.assertEqual((ns["p"].x, ns["p"].z), (1, 2))
        with self.assertRaises(Exception):
            ns["p"].x = 5


class Gang(unittest.TestCase):
    def test_one_liner(self):
        ns = run("gang Mood: ATE, MID, COOKED\n")
        self.assertEqual([m.name for m in ns["Mood"]], ["ATE", "MID", "COOKED"])

    def test_block_with_values_methods_and_base(self):
        ns = run("""\
            gang Size:
                SMALL
                BIG, HUGE
                cook shout(mee):
                    x = 1
                    serve mee.name.lower()
            gang Tier(str):
                S = "s"
            """)
        size = ns["Size"]
        self.assertEqual([m.value for m in size], [1, 2, 3])
        self.assertEqual(size.HUGE.shout(), "huge")
        self.assertEqual(ns["Tier"].S, "s")


class ShootRetry(unittest.TestCase):
    def test_retries_until_success(self):
        ns = run("""\
            calls = 0
            cook flaky():
                viral calls
                calls += 1
                fr calls < 3:
                    yeet ConnectionError("lag")
                serve "ok"
            shoot 5:
                result = flaky()
            fumble ConnectionError:
                result = "gave up"
            """)
        self.assertEqual((ns["result"], ns["calls"]), ("ok", 3))

    def test_handler_runs_after_last_try_and_finally_once(self):
        ns = run("""\
            tries = []
            done = []
            shoot 2:
                tries.append(1)
                yeet ValueError("nope")
            fumble ValueError:
                result = "handled"
            periodt:
                done.append(1)
            """)
        self.assertEqual((ns["result"], len(ns["tries"]), ns["done"]), ("handled", 2, [1]))

    def test_without_handler_reraises(self):
        with self.assertRaisesRegex(ValueError, "x"):
            run("n = []\nshoot 3:\n    n.append(1)\n    yeet ValueError('x')\nperiodt:\n    chill\n")

    def test_unmatched_error_is_not_retried(self):
        ns = {"n": []}
        with self.assertRaises(KeyError):
            run("shoot 3:\n    n.append(1)\n    yeet KeyError('k')\nfumble ValueError:\n    chill\n", ns)
        self.assertEqual(len(ns["n"]), 1)

    def test_dip_inside_is_refused(self):
        with self.assertRaisesRegex(SyntaxError, "shoot n"):
            run("doomscroll i in range(3):\n    shoot 2:\n        dip\n    fumble ValueError:\n        chill\n")

    def test_traceback_line_numbers(self):
        try:
            run("x = 1\nshoot 2:\n    yap(1 / 0)\nfumble KeyError:\n    chill\n")
        except ZeroDivisionError as exc:
            self.assertEqual(traceback.extract_tb(exc.__traceback__)[-1].lineno, 3)


class Speedrun(unittest.TestCase):
    def test_prints_time(self):
        err = io.StringIO()
        with redirect_stderr(err):
            run('speedrun:\n    chill\nspeedrun "sort":\n    chill\n')
        lines = err.getvalue().splitlines()
        self.assertRegex(lines[0], r"^speedrun line 1: \d+\.\d{3}s$")
        self.assertRegex(lines[1], r"^speedrun sort: ")


class Pipe(unittest.TestCase):
    def test_pipes(self):
        ns = run("""\
            nums = [3, 1, 2]
            a = nums |> tierlist |> howlongisit
            b = nums |> tierlist(reverse=nocap)
            c = "hi" |> str.upper
            d = 1 + 1 |> str
            e = {1} | {2}
            f = (nums
                |> goat)
            """)
        self.assertEqual([ns[k] for k in "abcdef"], [3, [3, 2, 1], "HI", "2", {1, 2}, 3])

    def test_eval_and_translate(self):
        self.assertEqual(slaython.slay_eval("[1, 2] |> howlongisit"), 2)
        self.assertEqual(transpile("x = [1] |> howlongisit"), "x = len([1])\n")


class VibeCheck(unittest.TestCase):
    def test_inline_tests_found_and_labelled(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "mathz.slay"), "w") as f:
                f.write('cook double(x): serve x * 2\n'
                        'vibecheck "works":\n    ongod double(2) == 4\n'
                        'vibecheck "fails":\n    ongod double(2) == 5, "mid"\n'
                        'maincharacter:\n    yeet "should not run in tests"\n')
            out = io.StringIO()
            self.assertEqual(run_tests([d], out=out), 1)
            text = out.getvalue()
            self.assertIn("vibecheck 'works'", text)
            self.assertIn("vibecheck 'fails': ongod failed: mid", text)

    def test_normal_run_skips_them(self):
        ns = run('vibecheck "never":\n    yeet "boom"\n')
        self.assertTrue(any(k.startswith("test_vibecheck_") for k in ns))


class NewBuiltins(unittest.TestCase):
    def test_builtins(self):
        ns = run("a = howlongisit([1, 2])\nb = pickone([9])\nc = headzortailz()\n")
        self.assertEqual((ns["a"], ns["b"]), (2, 9))
        self.assertIn(ns["c"], (True, False))


class Glowup(unittest.TestCase):
    def test_check_diff_and_write(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.slay")
            with open(path, "w") as f:
                f.write("def f(x):\n    if x is None:\n        return 1\nfr nocap:\n    yap(f(ghosted))\n")
            self.assertEqual(run_cli("glowup", "--check", d).returncode, 1)
            self.assertIn("+cook f(x):", run_cli("glowup", "--diff", d).stdout)
            self.assertEqual(run_cli("glowup", d).returncode, 0)
            with open(path) as f:
                self.assertEqual(f.read(), "cook f(x):\n    fr x literally ghosted:\n        serve 1\n"
                                           "fr nocap:\n    yap(f(ghosted))\n")
            self.assertEqual(run_cli("glowup", "--check", d).returncode, 0)


class ExampleFile(unittest.TestCase):
    def test_feed_app_example_runs(self):
        r = run_cli(os.path.join(ROOT, "examples", "feed_app.slay"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Post(caption='fit check', likes=420)", r.stdout)
        r = run_cli("test", os.path.join(ROOT, "examples", "feed_app.slay"))
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
