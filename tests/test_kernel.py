"""Tests for the Jupyter kernel (slaython/kernel.py).

The end-to-end tests start a real kernel and skip when ipykernel or
jupyter_client is not installed (pip install slaython[jupyter]).
"""

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout

from slaython import kernel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAVE_JUPYTER = all(importlib.util.find_spec(m) for m in ("ipykernel", "jupyter_client"))
needs_jupyter = unittest.skipUnless(HAVE_JUPYTER, "ipykernel and jupyter_client not installed")


def run_python(code, *args):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True,
                          env=env, cwd=ROOT, timeout=120)


class WithoutJupyter(unittest.TestCase):
    """These run everywhere: ipykernel must stay optional."""

    def test_import_slaython_does_not_import_jupyter(self):
        r = run_python(textwrap.dedent("""\
            import sys
            import slaython, slaython.kernel
            heavy = ("ipykernel", "IPython", "jupyter_client", "zmq")
            print([m for m in heavy if m in sys.modules])
            """))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "[]")

    def test_clear_message_when_ipykernel_is_missing(self):
        r = run_python(textwrap.dedent("""\
            import sys
            sys.modules["ipykernel"] = None  # makes `import ipykernel` fail
            from slaython.kernel import _module_main, main
            print(main(["install", "--prefix", sys.argv[1]]), _module_main(["-f", "x.json"]))
            """), tempfile.gettempdir())
        self.assertEqual(r.stdout.split(), ["1", "1"])
        self.assertIn("pip install slaython[jupyter]", r.stderr)

    def test_usage(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(kernel.main([]), 2)
            self.assertEqual(kernel.main(["nope"]), 2)
            self.assertEqual(kernel.main(["--help"]), 0)

    def test_kernel_json(self):
        spec = kernel.kernel_json()
        self.assertEqual(spec["argv"], [sys.executable, "-m", "slaython.kernel", "-f",
                                        "{connection_file}"])
        self.assertEqual(spec["display_name"], "Slaython")
        self.assertEqual(spec["language"], "slaython")

    def test_translate_lines_keeps_lines(self):
        src = "fr x:\n    yap(x)  # hi\nornah:\n    chill\n"
        out = kernel.translate_lines(src.splitlines(keepends=True))
        self.assertEqual("".join(out), "if x:\n    print(x)  # hi\nelse:\n    pass\n")

    def test_translate_lines_leaves_ipython_calls_alone(self):
        src = "get_ipython().system('echo fr cap')\n"
        self.assertEqual("".join(kernel.translate_lines([src])), src)

    def test_unclosed_bracket_is_a_plain_syntax_error(self):
        with self.assertRaises(SyntaxError) as cm:
            kernel.translate_lines(["yap((1,\n"])
        self.assertIs(type(cm.exception), SyntaxError)

    def test_check_source(self):
        self.assertEqual(kernel.check_source("fr x:"), "if x:")
        self.assertEqual(kernel.check_source("yap((1,"), "yap((1,")

    def test_slang_info(self):
        self.assertIn("print", kernel.slang_info("yap"))
        self.assertIn("elif", kernel.slang_info("fr"))
        self.assertIsNone(kernel.slang_info("print"))

    def test_completions(self):
        reply = {"status": "ok", "matches": ["yield"], "cursor_start": 4, "cursor_end": 6,
                 "metadata": {"_jupyter_types_experimental": [
                     {"start": 4, "end": 6, "text": "yield", "type": "keyword", "signature": ""}]}}
        reply = kernel.add_slang_completions(reply, "x = ye", 6)
        self.assertEqual(reply["matches"], ["yeet", "yield"])
        types = reply["metadata"]["_jupyter_types_experimental"]
        self.assertEqual([t["text"] for t in types], ["yeet", "yield"])
        empty = {"status": "ok", "matches": [], "cursor_start": 3, "cursor_end": 3, "metadata": {}}
        self.assertEqual(kernel.add_slang_completions(empty, "ya", 2)["matches"], ["yap"])
        for code in ("obj.ya", "pullup o", "outta os pullup pa"):
            reply = {"status": "ok", "matches": [], "cursor_start": 0, "cursor_end": 0,
                     "metadata": {}}
            self.assertEqual(kernel.add_slang_completions(reply, code, len(code))["matches"], [])

    def test_import_line_for_completion(self):
        self.assertEqual(kernel.import_line_for_completion("x = 1\noutta os pullup pa"),
                         "x = 1\nfrom  os import pa")
        self.assertEqual(kernel.import_line_for_completion("yap(pullup)"), "yap(pullup)")


@needs_jupyter
class InstallCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kernels = os.path.join(self.tmp.name, "share", "jupyter", "kernels")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "slaython.kernel", *args],
                              capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, PYTHONPATH=ROOT), cwd=ROOT)

    def test_install_and_remove(self):
        r = self.cli("install", "--prefix", self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.kernels, "slaython", "kernel.json"), encoding="utf-8") as f:
            spec = json.load(f)
        self.assertEqual(spec["argv"][1:], ["-m", "slaython.kernel", "-f", "{connection_file}"])
        self.assertTrue(os.path.exists(spec["argv"][0]))
        self.assertEqual(spec["display_name"], "Slaython")
        self.assertEqual(spec["language"], "slaython")
        r = self.cli("remove", "--prefix", self.tmp.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.kernels, "slaython")))
        self.assertEqual(self.cli("remove", "--prefix", self.tmp.name).returncode, 1)
        self.assertEqual(self.cli("list").returncode, 0)

    def test_custom_name(self):
        r = self.cli("install", "--prefix", self.tmp.name, "--name", "slay-dev",
                     "--display-name", "Slaython (dev)")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.kernels, "slay-dev", "kernel.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["display_name"], "Slaython (dev)")
        self.assertEqual(self.cli("install", "--prefix", self.tmp.name, "--name", "no way").returncode,
                         2)

    def test_remove_leaves_other_kernels_alone(self):
        other = os.path.join(self.kernels, "python3")
        os.makedirs(other)
        with open(os.path.join(other, "kernel.json"), "w", encoding="utf-8") as f:
            json.dump({"argv": [], "display_name": "Python 3", "language": "python"}, f)
        r = self.cli("remove", "--prefix", self.tmp.name, "--name", "python3")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(os.path.exists(other))


@needs_jupyter
class KernelEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from jupyter_client.kernelspec import KernelSpecManager
        from jupyter_client.manager import KernelManager
        cls.tmp = tempfile.TemporaryDirectory()
        with redirect_stdout(io.StringIO()):
            assert kernel.main(["install", "--prefix", cls.tmp.name]) == 0
        kdir = os.path.join(cls.tmp.name, "share", "jupyter", "kernels")
        cls.km = KernelManager(kernel_name="slaython",
                               kernel_spec_manager=KernelSpecManager(kernel_dirs=[kdir]))
        env = dict(os.environ, PYTHONPATH=ROOT)
        env.pop("SLAYTHON_VIBES", None)
        cls.log = open(os.path.join(cls.tmp.name, "kernel.log"), "w+", encoding="utf-8")
        cls.km.start_kernel(env=env, cwd=cls.tmp.name, stdout=cls.log, stderr=cls.log)
        cls.kc = cls.km.client()
        cls.kc.start_channels()
        try:
            cls.kc.wait_for_ready(timeout=120)
        except RuntimeError:
            cls.log.seek(0)
            sys.stderr.write(cls.log.read())
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.kc.stop_channels()
        cls.km.shutdown_kernel(now=True)
        cls.log.close()
        cls.tmp.cleanup()

    def run_cell(self, code, stdin=None):
        """Run a cell; return (reply content, stdout text, result text, error text)."""
        out, results, errors = [], [], []

        def hook(msg):
            kind, content = msg["msg_type"], msg["content"]
            if kind == "stream":
                out.append(content["text"])
            elif kind == "execute_result":
                results.append(content["data"]["text/plain"])
            elif kind == "error":
                errors.append("\n".join(content["traceback"]))

        reply = self.kc.execute_interactive(
            code, output_hook=hook, timeout=60, allow_stdin=stdin is not None,
            stdin_hook=(lambda msg: self.kc.input(stdin)) if stdin is not None else None)
        return reply["content"], "".join(out), "\n".join(results), "\n".join(errors)

    def shell_request(self, method, *args):
        getattr(self.kc, method)(*args)
        return self.kc.get_shell_msg(timeout=30)["content"]

    def test_kernel_info(self):
        info = self.shell_request("kernel_info")
        self.assertEqual(info["implementation"], "slaython")
        self.assertEqual(info["language_info"]["name"], "slaython")
        self.assertEqual(info["language_info"]["file_extension"], ".slay")
        self.assertIn("Slaython", info["banner"])

    def test_slang_and_display(self):
        reply, out, result, _ = self.run_cell('yap("hi bestie")\nx = 21\nx * 2')
        self.assertEqual(reply["status"], "ok")
        self.assertEqual(out, "hi bestie\n")
        self.assertEqual(result, "42")

    def test_block_and_state_between_cells(self):
        self.run_cell(textwrap.dedent("""\
            cook vibe(n):
                doomscroll i in range(n):
                    fr i % 2 == 0:
                        drop "even"
                    ornah:
                        drop "odd"
            """))
        _, _, result, _ = self.run_cell("list(vibe(3))")
        self.assertEqual(result, "['even', 'odd', 'even']")

    def test_runtime_error_traceback(self):
        reply, _, _, err = self.run_cell("# comment\nxs = [1, 2]\nyap(xs[0] / 0)")
        self.assertEqual(reply["status"], "error")
        self.assertEqual(reply["ename"], "ZeroDivisionError")
        self.assertRegex(err, r"Cell In\[\d+\], line 3, in <module>")
        self.assertIn("    yap(xs[0] / 0)\n        ~~~~~~^~~", err)
        self.assertIn("real talk: bro really tried to divide by zero", err)
        self.assertNotIn("interactiveshell.py", err)
        self.assertEqual(reply["traceback"], err.split("\n"))

    def test_error_in_function_from_earlier_cell(self):
        self.run_cell("cook boom(v):\n    serve 10 / v")
        _, _, _, err = self.run_cell("%time boom(0)")
        self.assertIn("    serve 10 / v", err)
        self.assertNotIn("execution.py", err)

    def test_vibes_off(self):
        try:
            self.run_cell("%env SLAYTHON_VIBES=0")
            _, _, _, err = self.run_cell('{}["k"]')
        finally:
            self.run_cell("%env SLAYTHON_VIBES=1")
        self.assertIn("KeyError: 'k'", err)
        self.assertNotIn("real talk", err)

    def test_syntax_error_points_at_slang(self):
        reply, _, _, err = self.run_cell("x = 1\nfr x > 3\n    yap(1)")
        self.assertEqual(reply["ename"], "SyntaxError")
        self.assertRegex(err, r"Cell In\[\d+\], line 2\n    fr x > 3\n")
        self.assertIn("real talk:", err)

    def test_translator_error(self):
        reply, _, _, err = self.run_cell("deadass LIMIT = 1\nLIMIT = 2")
        self.assertEqual(reply["ename"], "SyntaxError")
        self.assertRegex(err, r"Cell In\[\d+\], line 2\n    LIMIT = 2")
        self.assertIn("deadass", err)

    def test_magics_and_shell(self):
        _, out, _, _ = self.run_cell("%time yap(goat(1, 2))")
        self.assertTrue(out.startswith("2\n"))
        self.assertIn("Wall time", out)
        _, out, _, _ = self.run_cell('%%time\nfr nocap:\n    yap("timed")')
        self.assertTrue(out.startswith("timed\n"))
        _, out, _, _ = self.run_cell("!echo fr cap")
        self.assertEqual(out.strip(), "fr cap")

    def test_help(self):
        reply, out, _, _ = self.run_cell("yap?")
        self.assertIn("yap  ->  print", out)
        pages = [p["data"]["text/plain"] for p in reply.get("payload", []) if "data" in p]
        self.assertTrue(any("print" in p for p in pages), pages)

    def test_hmu_reads_stdin(self):
        _, out, _, _ = self.run_cell('name = hmu("name? ")\nyap("hi", name)', stdin="mia")
        self.assertIn("hi mia", out)

    def test_pipe_and_retry(self):
        _, _, result, _ = self.run_cell("[3, 1, 2] |> tierlist |> howlongisit")
        self.assertEqual(result, "3")
        _, _, result, _ = self.run_cell(textwrap.dedent("""\
            tries = 0
            cook flaky():
                viral tries
                tries += 1
                fr tries < 3:
                    yeet "nah"
                serve tries
            shoot 5:
                r = flaky()
            fumble skillissue:
                r = ghosted
            r
            """))
        self.assertEqual(result, "3")
        _, _, _, err = self.run_cell("# c\n\nz = 0 |> (nohead v: 1 / v)")
        self.assertRegex(err, r"Cell In\[\d+\], line 3, in <lambda>")

    def test_is_complete(self):
        reply = self.shell_request("is_complete", "fr x:")
        self.assertEqual(reply, {"status": "incomplete", "indent": "    "})
        self.assertEqual(self.shell_request("is_complete", "yap(1")["status"], "incomplete")
        self.assertEqual(self.shell_request("is_complete", "yap(1)")["status"], "complete")
        self.assertEqual(self.shell_request("is_complete", "fr x:\n    yap(x)\n")["status"],
                         "complete")

    def test_complete(self):
        reply = self.shell_request("complete", "doomsc", 6)
        self.assertIn("doomscroll", reply["matches"])
        self.assertEqual((reply["cursor_start"], reply["cursor_end"]), (0, 6))
        reply = self.shell_request("complete", "pullup o", 8)
        self.assertIn("os", reply["matches"])

    def test_inspect(self):
        reply = self.shell_request("inspect", "yap(", 3)
        self.assertTrue(reply["found"])
        self.assertIn("yap  ->  print", reply["data"]["text/plain"])
        self.assertIn("sep", reply["data"]["text/plain"])

    def test_slang_sheet(self):
        _, _, result, _ = self.run_cell("slang")
        self.assertTrue(re.search(r"doomscroll\s+for", result))


if __name__ == "__main__":
    unittest.main()
