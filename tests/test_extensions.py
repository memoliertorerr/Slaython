import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout

import slaython
from slaython import transpile
from slaython.testing import run_tests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args, env_extra=None):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-m", "slaython", *args], capture_output=True,
                          text=True, env=env, cwd=ROOT, timeout=60)


class RenamedKeywords(unittest.TestCase):
    def test_new_words(self):
        src = textwrap.dedent("""\
            shoot:
                f = nohead x: x orr 1
                lockedin cap:
                    chill
            fumble ValueError:
                ongod nocap
            """)
        self.assertEqual(transpile(src), textwrap.dedent("""\
            try:
                f = lambda x: x or 1
                while False:
                    pass
            except ValueError:
                assert True
            """))

    def test_and_in_stay_plain(self):
        self.assertEqual(transpile("fr a and b in c: chill"), "if a and b in c: pass")


class Builtins(unittest.TestCase):
    def test_slang_builtins(self):
        ns = {}
        slaython.slay(textwrap.dedent("""\
            blueprint A:
                cook who(mee):
                    serve whoisyou(mee).__name__
            out = [goat(1, 5), flop(1, 5), tierlist([2, 1]), giving(1, int),
                   A().who(), skillissue literally Exception]
            """), ns)
        self.assertEqual(ns["out"], [5, 1, [1, 2], True, "A", True])

    def test_touchgrass_exits(self):
        r = run_cli("-c", "yap('a')\ntouchgrass(3)\nyap('b')")
        self.assertEqual((r.returncode, r.stdout), (3, "a\n"))


class RunItFoo(unittest.TestCase):
    def test_repeats(self):
        ns = {}
        slaython.slay("n = 0\nrunitfoo 2 + 1:\n    n += 1\n", ns)
        self.assertEqual(ns["n"], 3)

    def test_plain_name_untouched(self):
        self.assertEqual(transpile("runitfoo = 3"), "runitfoo = 3")

    def test_one_line_body(self):
        self.assertEqual(transpile("runitfoo n: yap(1)"), "for _ in range(n): print(1)")


class YeetString(unittest.TestCase):
    def test_plain_string(self):
        self.assertEqual(transpile('yeet "bad"'), 'raise Exception("bad")')
        self.assertEqual(transpile('yeet "a" "b" outta e'), 'raise Exception("a" "b") from e')

    def test_fstring_and_runtime(self):
        with self.assertRaisesRegex(Exception, "too big: 5"):
            slaython.slay('x = 5\nyeet f"too big: {x}"', {})

    def test_normal_yeet_untouched(self):
        self.assertEqual(transpile('yeet ValueError("x")'), 'raise ValueError("x")')
        self.assertEqual(transpile('yeet "a".upper()'), 'raise "a".upper()')


class Deadass(unittest.TestCase):
    def test_declares(self):
        self.assertEqual(transpile("deadass MAX = 3\nyap(MAX)\n"), "MAX = 3\nprint(MAX)\n")
        self.assertEqual(transpile("deadass MAX: int = 3"), "MAX: int = 3")

    def test_reassign_is_an_error(self):
        for bad in ("MAX = 4", "MAX += 1", "cook f():\n    MAX = 1", "cancel MAX"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(SyntaxError, "deadass"):
                    transpile("deadass MAX = 3\n" + bad + "\n")

    def test_other_uses_are_fine(self):
        transpile("deadass MAX = 3\nx = MAX + 1\nobj.MAX = 2\nf(MAX=1)\n")

    def test_needs_value(self):
        with self.assertRaisesRegex(SyntaxError, "needs a name and a value"):
            transpile("deadass MAX\n")


class Helpers(unittest.TestCase):
    def test_lowkeysus_prints_and_returns(self):
        err = io.StringIO()
        with redirect_stderr(err):
            ns = {}
            slaython.slay("total = 21\ny = lowkeysus(total *\n    2)\n", ns)
        self.assertEqual(ns["y"], 42)
        self.assertEqual(err.getvalue(), "lowkeysus line 2: total * 2 = 42\n")

    def test_lowkeysus_keeps_line_numbers(self):
        src = "a = 1\nlowkeysus(\n  a,\n  a)\nb = 2\n"
        self.assertEqual(transpile(src).count("\n"), src.count("\n"))

    def test_bedrot(self):
        self.assertIn("sleep", repr(slaython.bedrot))
        slaython.slay("bedrot(0)", {})


class Vibes(unittest.TestCase):
    def test_no_vibes_flag_and_env(self):
        on = run_cli("-c", "1/0")
        self.assertIn("💀", on.stderr)
        self.assertNotIn("💀", run_cli("--no-vibes", "-c", "1/0").stderr)
        self.assertNotIn("💀", run_cli("-c", "1/0", env_extra={"SLAYTHON_VIBES": "0"}).stderr)


class TestRunner(unittest.TestCase):
    def test_example_suite_passes(self):
        out = io.StringIO()
        code = run_tests([os.path.join(ROOT, "examples", "testing")], out=out)
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("4 W, 0 L", out.getvalue())

    def test_failures_are_ls(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "test_bad.slay"), "w") as f:
                f.write("cook test_ok():\n    chill\ncook test_bad():\n    ongod 1 == 2, 'math'\n")
            out = io.StringIO()
            self.assertEqual(run_tests([d], out=out), 1)
            self.assertIn("test_bad.slay::test_bad: ongod failed: math\n", out.getvalue())
            self.assertNotIn("..", out.getvalue())
            self.assertIn("1 W, 1 L", out.getvalue())

    def test_no_tests(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run_tests([d], out=io.StringIO()), 5)


class AutoImport(unittest.TestCase):
    def test_pth_lets_plain_python_import_slay(self):
        with tempfile.TemporaryDirectory() as site_dir, tempfile.TemporaryDirectory() as code:
            r = run_cli("autoimport", "on", "--dir", site_dir)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(code, "slaymod_auto.slay"), "w") as f:
                f.write("VALUE = nocap\n")
            env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, code]))
            script = f"import site; site.addsitedir({site_dir!r}); import slaymod_auto; print(slaymod_auto.VALUE)"
            r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(r.stdout.strip(), "True", r.stderr)
            self.assertIn("off", run_cli("autoimport", "off", "--dir", site_dir).stdout)
            self.assertFalse(os.listdir(site_dir))


@unittest.skipUnless(__import__("importlib").util.find_spec("IPython"), "IPython not installed")
class Jupyter(unittest.TestCase):
    def test_cell_and_line_magic(self):
        from IPython.core.interactiveshell import InteractiveShell
        ip = InteractiveShell.instance()
        ip.run_line_magic("load_ext", "slaython")
        out = io.StringIO()
        with redirect_stdout(out):
            ip.run_cell_magic("slay", "", "nums = tierlist([3, 1])\nyap(goat(nums))\n")
        self.assertEqual(out.getvalue(), "3\n")
        self.assertEqual(ip.run_line_magic("slay", "flop(nums) fr nocap ornah 0"), 1)


if __name__ == "__main__":
    unittest.main()
