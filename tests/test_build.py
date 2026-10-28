import ast
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout

from slaython import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")
# Example scripts with output that doesn't change from run to run.
EXAMPLE_SCRIPTS = [
    "async_match", "classes", "errors", "extras", "feed_app", "fizzbuzz", "generators", "hello",
    "interop/use_from_slaython", "testing/feed", "testing/test_feed",
]

PROJECT = {
    "app.slay": """\
        # A script that uses the squadgoals package.
        outta squadgoals pullup Post, Mood, LIMIT, top_captions
        outta squadgoals.stats pullup flaky_total, timed_sum

        posts = [Post("fit", 420), Post("mid", 12), Post("ratio", 77)]
        yap(posts[0], posts[0].mood().name, Mood.COOKED.value, LIMIT)
        yap(posts |> top_captions)
        yap(flaky_total([1, 2, 3]))
        yap(timed_sum(range(10)))
        lowkeysus(2 * howlongisit(posts))
        yap(headzortailz() |> whoisyou)
        yap(pickone([7]))
        bedrot(0)

        maincharacter:
            yap("main character energy")
        """,
    "squadgoals/__init__.slay": """\
        \"\"\"A Slaython package.\"\"\"
        outta .stats pullup flaky_total

        deadass LIMIT = 2

        gang Mood: ATE, MID, COOKED


        lore Post:
            caption: str
            likes: int = 0

            cook mood(mee):
                serve Mood.ATE fr mee.likes >= 100 ornah Mood.MID


        cook captions(posts):
            serve [p.caption doomscroll p in posts][:LIMIT]


        cook top_captions(posts):
            serve posts |> tierlist(key=nohead p: p.likes, reverse=nocap) |> captions
        """,
    "squadgoals/stats.slay": """\
        pullup json
        outta pathlib pullup Path
        outta .helper pullup double

        tries = 0


        cook flaky():
            viral tries
            tries += 1
            fr tries < 3:
                yeet ConnectionError("lag")
            serve tries


        cook flaky_total(nums):
            shoot 5:
                got = flaky()
            fumble ConnectionError:
                got = -1
            serve sum(nums) + got


        cook timed_sum(nums):
            speedrun "sum":
                total = nums |> sum
            speedrun:
                total = double(total)
            serve total


        cook settings():
            serve json.loads((Path(__file__).parent / "settings.json").read_text())
        """,
    "squadgoals/helper.py": """\
        def double(x):
            return x * 2
        """,
    "squadgoals/settings.json": '{"vibe": "immaculate"}\n',
    "squadgoals/sub/__init__.slay": "",
    "squadgoals/sub/deep.slay": """\
        gang Level:
            LOW
            HIGH


        cook levels():
            serve [level.name doomscroll level in Level]
        """,
    "squadgoals/__main__.slay": """\
        outta squadgoals.stats pullup settings
        outta squadgoals.sub.deep pullup levels

        yap(settings()["vibe"], levels())
        """,
    "notes.txt": "not code, still copied\n",
    ".secret/hidden.slay": "yap('never built')\n",
    "__pycache__/junk.pyc": "",
}


def write_tree(root, files):
    for rel, text in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(text))


def normalize(text):
    """Timings differ between runs."""
    return re.sub(r"(speedrun [^:\n]*: )\d+\.\d+s", r"\1Xs", text)


def run_build(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = build.main(list(args))
    return code, out.getvalue(), err.getvalue()


class PlainPython:
    """A virtualenv without Slaython in it, to run the built code."""

    def __init__(self, folder):
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", folder],
                       check=True, capture_output=True, timeout=120)
        bindir = "Scripts" if os.name == "nt" else "bin"
        self.python = os.path.join(folder, bindir, "python.exe" if os.name == "nt" else "python")
        self.purelib = self.run("-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])",
                                cwd=folder).stdout.strip()

    def run(self, *args, cwd, stdin=""):
        # -E: ignore PYTHONPATH and friends, -s: no user site-packages. Not -I, because
        # that would also drop the script's own folder from sys.path.
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run([self.python, "-E", "-s", *args], cwd=cwd, input=stdin,
                              capture_output=True, text=True, env=env, timeout=60)


def run_slaython(*args, cwd=ROOT, stdin=""):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, *args], cwd=cwd, input=stdin, capture_output=True,
                          text=True, env=env, timeout=60)


class BuildTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        try:
            cls.plain = PlainPython(os.path.join(cls.tmp, "venv"))
        except (OSError, subprocess.SubprocessError) as exc:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest(f"can't make a virtualenv: {exc}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def assertSameRun(self, built, original):
        self.assertEqual(built.returncode, original.returncode, built.stderr)
        self.assertEqual(built.stdout, original.stdout)
        self.assertEqual(normalize(built.stderr), normalize(original.stderr))


class PlainPythonHasNoSlaython(BuildTestCase):
    def test_import_fails(self):
        proc = self.plain.run("-c", "import slaython", cwd=self.tmp)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("No module named 'slaython'", proc.stderr)


class Examples(BuildTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.out = os.path.join(cls.tmp, "examples-py")
        cls.code, cls.stdout, cls.stderr = run_build(EXAMPLES, "-o", cls.out)

    def test_build_succeeds(self):
        self.assertEqual(self.code, 0, self.stderr)
        self.assertIn("built", self.stdout)

    def test_every_slay_file_becomes_python(self):
        for path in glob.glob(os.path.join(EXAMPLES, "**", "*.slay"), recursive=True):
            rel = os.path.relpath(path, EXAMPLES)[:-len(".slay")] + ".py"
            self.assertTrue(os.path.isfile(os.path.join(self.out, rel)), rel)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "interop", "helpers.py")))

    def test_outputs_match_slaython(self):
        for name in EXAMPLE_SCRIPTS:
            with self.subTest(example=name):
                built = self.plain.run(os.path.join(self.out, *name.split("/")) + ".py",
                                       cwd=self.tmp, stdin="kai\n")
                original = run_slaython("-m", "slaython", f"examples/{name}.slay", stdin="kai\n")
                self.assertSameRun(built, original)

    def test_package_imports_from_python(self):
        code = "from squadpkg.ranking import to_json; print(to_json({'a': [1], 'b': [3]}))"
        built = self.plain.run("-c", code, cwd=os.path.join(self.out, "interop"))
        original = run_slaython("-c", "import slaython; " + code,
                                cwd=os.path.join(EXAMPLES, "interop"))
        self.assertSameRun(built, original)

    def test_python_that_needs_slaython_gets_a_warning(self):
        self.assertIn("use_from_python.py: imports slaython", self.stderr)


class Project(BuildTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = os.path.join(cls.tmp, "proj")
        write_tree(cls.src, PROJECT)
        cls.out = os.path.join(cls.tmp, "proj-py")
        cls.code, cls.stdout, cls.stderr = run_build(cls.src, "-o", cls.out)

    def read(self, rel):
        with open(os.path.join(self.out, *rel.split("/")), encoding="utf-8") as f:
            return f.read()

    def test_files(self):
        self.assertEqual(self.code, 0, self.stderr)
        for rel in ["app.py", "slaython_runtime.py", "notes.txt", "squadgoals/__init__.py",
                    "squadgoals/stats.py", "squadgoals/helper.py", "squadgoals/settings.json",
                    "squadgoals/__main__.py", "squadgoals/_slaython_runtime.py",
                    "squadgoals/sub/__init__.py", "squadgoals/sub/deep.py"]:
            self.assertTrue(os.path.isfile(os.path.join(self.out, *rel.split("/"))), rel)
        for rel in [".secret", "__pycache__", "squadgoals/sub/_slaython_runtime.py"]:
            self.assertFalse(os.path.exists(os.path.join(self.out, *rel.split("/"))), rel)

    def test_header_and_runtime_references(self):
        self.assertTrue(self.read("app.py").endswith(
            "# Generated from app.slay by slaython build.\n"))
        self.assertTrue(self.read("squadgoals/sub/deep.py").endswith(
            "# Generated from squadgoals/sub/deep.slay by slaython build.\n"))
        self.assertIn('__import__("slaython_runtime")', self.read("app.py"))
        self.assertIn('__import__("squadgoals._slaython_runtime")._slaython_runtime',
                      self.read("squadgoals/sub/deep.py"))
        for path in glob.glob(os.path.join(self.out, "**", "*.py"), recursive=True):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertNotRegex(text, r"""__import__\(['"]slaython['"]\)""", path)

    def test_script_matches_slaython(self):
        built = self.plain.run(os.path.join(self.out, "app.py"), cwd=self.tmp)
        original = run_slaython("-m", "slaython", os.path.join(self.src, "app.slay"))
        self.assertSameRun(built, original)
        self.assertIn("main character energy", built.stdout)
        self.assertIn("lowkeysus line 10: 2 * howlongisit(posts) = 6", built.stderr)
        self.assertIn("speedrun sum:", built.stderr)

    def test_package_main_matches_slaython(self):
        built = self.plain.run("-m", "squadgoals", cwd=self.out)
        original = run_slaython(
            "-c", "import slaython, runpy; runpy.run_module('squadgoals', run_name='__main__')",
            cwd=self.src)
        self.assertSameRun(built, original)
        self.assertEqual(built.stdout, "immaculate ['LOW', 'HIGH']\n")

    def test_installed_package(self):
        target = os.path.join(self.plain.purelib, "squadgoals")
        shutil.copytree(os.path.join(self.out, "squadgoals"), target)
        self.addCleanup(shutil.rmtree, target, True)
        code = ("from squadgoals import Post, top_captions; from squadgoals.sub.deep import levels; "
                "print(Post('a', 1), top_captions([Post('a', 1), Post('b', 5)]), levels())")
        proc = self.plain.run("-c", code, cwd=self.tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "Post(caption='a', likes=1) ['b', 'a'] ['LOW', 'HIGH']\n")


class Problems(BuildTestCase):
    def test_bad_files_are_reported_and_good_ones_built(self):
        src = os.path.join(self.tmp, "broken")
        write_tree(src, {
            "good.slay": "yap('fine')\n",
            "bad.slay": "x = 1\n\nfr x\n    chill\n",
            "const.slay": "deadass X = 1\nX = 2\n",
        })
        out = os.path.join(self.tmp, "broken-py")
        code, _, err = run_build(src, "-o", out)
        self.assertEqual(code, 1)
        self.assertIn("bad.slay:3", err)
        self.assertIn("const.slay:2", err)
        self.assertTrue(os.path.isfile(os.path.join(out, "good.py")))
        self.assertFalse(os.path.exists(os.path.join(out, "bad.py")))

    def test_single_file(self):
        src = os.path.join(self.tmp, "solo")
        write_tree(src, {"solo.slay": "#!/usr/bin/env slaython\nlowkeysus(1 + 1)\n"})
        out = os.path.join(self.tmp, "solo-py")
        code, _, err = run_build(os.path.join(src, "solo.slay"), "-o", out)
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(os.listdir(out)), [".slaython-build", "slaython_runtime.py", "solo.py"])
        with open(os.path.join(out, "solo.py")) as f:
            lines = f.read().splitlines()
        self.assertEqual((lines[0], lines[-1]),
                         ("#!/usr/bin/env python3", "# Generated from solo.slay by slaython build."))
        proc = self.plain.run(os.path.join(out, "solo.py"), cwd=self.tmp)
        self.assertEqual((proc.returncode, proc.stderr), (0, "lowkeysus line 2: 1 + 1 = 2\n"))

    def test_coding_cookie_becomes_utf8(self):
        src = os.path.join(self.tmp, "latin")
        os.makedirs(src)
        with open(os.path.join(src, "latin.slay"), "wb") as f:
            f.write("# -*- coding: latin-1 -*-\nyap('caf\xe9')\n".encode("latin-1"))
        out = os.path.join(self.tmp, "latin-py")
        self.assertEqual(run_build(src, "-o", out)[0], 0)
        proc = self.plain.run(os.path.join(out, "latin.py"), cwd=self.tmp)
        self.assertEqual(proc.stdout, "caf\xe9\n", proc.stderr)

    def test_clean(self):
        src = os.path.join(self.tmp, "cleanme")
        write_tree(src, {"a.slay": "yap(1)\n"})
        out = os.path.join(self.tmp, "cleanme-py")
        write_tree(out, {"precious.txt": "not from a build\n"})
        code, _, err = run_build(src, "-o", out, "--clean")
        self.assertEqual(code, 2)
        self.assertIn("not cleaning", err)
        self.assertTrue(os.path.exists(os.path.join(out, "precious.txt")))
        os.remove(os.path.join(out, "precious.txt"))
        self.assertEqual(run_build(src, "-o", out)[0], 0)
        write_tree(out, {"stale.py": ""})
        self.assertEqual(run_build(src, "-o", out, "--clean")[0], 0)
        self.assertFalse(os.path.exists(os.path.join(out, "stale.py")))
        self.assertTrue(os.path.exists(os.path.join(out, "a.py")))

    def test_output_cannot_hold_the_source(self):
        src = os.path.join(self.tmp, "inner", "src")
        write_tree(src, {"a.slay": "yap(1)\n"})
        self.assertEqual(run_build(src, "-o", os.path.join(self.tmp, "inner"))[0], 2)

    def test_output_inside_source_is_skipped(self):
        src = os.path.join(self.tmp, "nested")
        write_tree(src, {"a.slay": "yap(1)\n"})
        out = os.path.join(src, "out")
        self.assertEqual(run_build(src, "-o", out)[0], 0)
        self.assertEqual(run_build(src, "-o", out)[0], 0)  # second run must not copy out/ into out/
        self.assertFalse(os.path.exists(os.path.join(out, "out")))


class Runtime(unittest.TestCase):
    def test_defines_every_helper_the_translator_emits(self):
        used = set()
        for path in glob.glob(os.path.join(ROOT, "slaython", "*.py")):
            if os.path.basename(path) == "build.py":
                continue
            with open(path, encoding="utf-8") as f:
                used |= set(re.findall(r"""__import__\(\s*['"]slaython['"]\s*\)\.(\w+)""", f.read()))
        self.assertTrue({"_sus", "Lore", "_gang_values", "_attempts", "_speedrun"} <= used, used)
        missing = used - build.runtime_names()
        self.assertFalse(missing, f"slaython/helpers.py has names the build runtime lacks: {missing}")

    def test_runtime_does_not_import_slaython(self):
        tree = ast.parse(build.runtime_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(any(a.name.startswith("slaython") for a in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                self.assertFalse((node.module or "").startswith("slaython"))
        namespace = {}
        exec(compile(build.runtime_source(), "slaython_runtime.py", "exec"), namespace)
        self.assertEqual(namespace["_gang_values"](2).__class__, tuple)

    def test_rewrite_only_touches_slaython_imports(self):
        code = ('x = __import__("slaython")._sus("a", 1, 2)\n'
                "y = __import__('slaython').Lore\n"
                's = \'__import__("slaython")\'\n'
                'z = __import__("enum").Enum\n')
        new = build.rewrite_runtime_refs(code, '__import__("rt")')
        self.assertEqual(new, ('x = __import__("rt")._sus("a", 1, 2)\n'
                               'y = __import__("rt").Lore\n'
                               's = \'__import__("slaython")\'\n'
                               'z = __import__("enum").Enum\n'))


if __name__ == "__main__":
    unittest.main()
