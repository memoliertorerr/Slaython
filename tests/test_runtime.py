import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout

import slaython
from slaython.repl import SlayConsole

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


def run_cli(*args, stdin=""):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "slaython", *args], input=stdin,
                          capture_output=True, text=True, env=env, cwd=ROOT, timeout=60)


class InlineApi(unittest.TestCase):
    def test_slay_runs_in_callers_namespace(self):
        slaython.slay("result = [x doomscroll x canon range(4) fr x % 2 == 0]")
        self.assertEqual(locals()["result"], [0, 2])

    def test_slay_eval(self):
        self.assertIs(slaython.slay_eval("ghosted literally ghosted"), True)
        self.assertEqual(slaython.slay_eval("(npc x: x + 1)(1)"), 2)

    def test_full_program(self):
        out = io.StringIO()
        with redirect_stdout(out):
            slaython.slay(textwrap.dedent("""\
                blueprint A:
                    cook hi(self):
                        serve "a"
                blueprint B(A):
                    cook hi(self):
                        serve og().hi() + "b"
                cook gen():
                    tryna:
                        drop 1
                        yeet KeyError("k")
                    crashout KeyError:
                        drop 2
                    periodt:
                        drop 3
                yap(B().hi(), list(gen()))
                """), {})
        self.assertEqual(out.getvalue(), "ab [1, 2, 3]\n")


class Imports(unittest.TestCase):
    def test_python_imports_slay_module_and_package(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "slaymod_t.slay"), "w") as f:
                f.write("cook double(x):\n    serve x * 2\n")
            os.mkdir(os.path.join(d, "slaypkg_t"))
            with open(os.path.join(d, "slaypkg_t", "__init__.slay"), "w") as f:
                f.write("outta .inner pullup VALUE\n")
            with open(os.path.join(d, "slaypkg_t", "inner.slay"), "w") as f:
                f.write("VALUE = nocap\n")
            sys.path.insert(0, d)
            try:
                import slaymod_t
                import slaypkg_t
                self.assertEqual(slaymod_t.double(21), 42)
                self.assertIs(slaypkg_t.VALUE, True)
                self.assertTrue(slaymod_t.__file__.endswith(".slay"))
            finally:
                sys.path.remove(d)
                for name in ("slaymod_t", "slaypkg_t", "slaypkg_t.inner"):
                    sys.modules.pop(name, None)

    def test_install_is_idempotent(self):
        before = list(sys.path_hooks)
        slaython.install()
        slaython.install()
        self.assertEqual(sys.path_hooks, before)


class Cli(unittest.TestCase):
    def test_examples_run(self):
        for name in ("fizzbuzz", "classes", "errors", "generators", "async_match"):
            r = run_cli(os.path.join(EXAMPLES, name + ".slay"))
            self.assertEqual(r.returncode, 0, name + r.stderr)
        self.assertIn("FizzBuzz", run_cli(os.path.join(EXAMPLES, "fizzbuzz.slay")).stdout)

    def test_hello_reads_input(self):
        r = run_cli(os.path.join(EXAMPLES, "hello.slay"), stdin="kai\n")
        self.assertIn("ayy kai", r.stdout)

    def test_interop_examples(self):
        r = run_cli(os.path.join(EXAMPLES, "interop", "use_from_slaython.slay"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SLAYTHON!!!", r.stdout)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, os.path.join(EXAMPLES, "interop", "use_from_python.py")],
                           capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ranking: ['mia', 'kai', 'jay']", r.stdout)

    def test_runtime_error_shows_slang_line_and_vibe(self):
        r = run_cli("-c", "x = {}\nyap(x['nope'])")
        self.assertEqual(r.returncode, 1)
        self.assertIn("yap(x['nope'])", r.stderr)
        self.assertIn("KeyError", r.stderr)
        self.assertIn("ghosted", r.stderr)
        self.assertNotIn("slaython/runner.py", r.stderr)

    def test_syntax_error_points_at_slang(self):
        r = run_cli("-c", "fr nocap\n    chill")
        self.assertEqual(r.returncode, 1)
        self.assertIn("fr nocap", r.stderr)
        self.assertIn("SyntaxError", r.stderr)

    def test_argv(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "args.slay")
            with open(p, "w") as f:
                f.write("pullup sys\nyap(sys.argv[1:])\n")
            r = run_cli("run", p, "a", "b")
            self.assertEqual(r.stdout.strip(), "['a', 'b']")

    def test_translate_and_slayify(self):
        r = run_cli("translate", os.path.join(EXAMPLES, "fizzbuzz.slay"))
        self.assertIn("elif n % 3 == 0:", r.stdout)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.py")
            with open(p, "w") as f:
                f.write("def drop():\n    return True\n")
            r = run_cli("slayify", p)
            self.assertEqual(r.stdout, "cook drop():\n    serve nocap\n")
            self.assertIn("'drop' is a Slaython keyword", r.stderr)

    def test_keywords_table(self):
        r = run_cli("keywords")
        self.assertIn("doomscroll", r.stdout)


class Repl(unittest.TestCase):
    def test_multiline_block(self):
        console = SlayConsole(locals={})
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertTrue(console.push("fr nocap:"))
            self.assertTrue(console.push("    yap('yes')"))
            self.assertFalse(console.push(""))
            self.assertTrue(console.push("yap(1,"))
            self.assertFalse(console.push("2)"))
        self.assertEqual(out.getvalue(), "yes\n1 2\n")


if __name__ == "__main__":
    unittest.main()
