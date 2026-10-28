import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout

from slaython import lint
from slaython.lint import CODES, lint_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


def problems(src, filename="t.slay", **kw):
    return lint_source(textwrap.dedent(src), filename, **kw)


def codes(src, filename="t.slay"):
    return [(p.code, p.line) for p in problems(src, filename)]


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = lint.main(list(args))
    return code, out.getvalue(), err.getvalue()


class Basics(unittest.TestCase):
    def test_clean_code(self):
        self.assertEqual(problems("""
            outta math pullup sqrt

            cook hyp(a, b):
                serve sqrt(a * a + b * b)

            yap(hyp(3, 4))
        """), [])

    def test_format_and_column(self):
        [p] = problems("total = 1\nyap(totl)\n", "app.slay")
        self.assertEqual(str(p), "app.slay:2:5: SL101 who is totl? it's never defined (typo for total?)")

    def test_columns_point_into_slang(self):
        # `fr nah x orr` becomes `if not x or`: the column must still match the .slay line
        line = "fr nah x orr totl:"
        [p] = problems(f"x = 1\n{line}\n    chill\n")
        self.assertEqual((p.line, p.col), (2, line.index("totl") + 1))

    def test_columns_after_non_ascii(self):
        line = 'fr nah x: yap("éé", nope)'
        [p] = problems(f'x = 1\n{line}\n')
        self.assertEqual(p.col, line.index("nope") + 1)

    def test_every_code_documented(self):
        for code in CODES:
            self.assertIn(code, lint.__doc__)


class Undefined(unittest.TestCase):
    def test_typo(self):
        self.assertEqual(codes("yap(nope)\n"), [("SL101", 1)])

    def test_no_suggestion(self):
        [p] = problems("yap(qqqzzz)\n")
        self.assertIn("(typo?)", p.message)

    def test_builtins_and_slang_builtins(self):
        self.assertEqual(problems("yap(howlongisit([1]), goat(1, 2), len, print, __name__)\n"), [])

    def test_defined_later_used_in_function(self):
        self.assertEqual(problems("""
            cook main():
                serve helper() + LIMIT

            cook helper():
                serve 1

            LIMIT = 3
        """), [])

    def test_used_before_defined_at_module_level(self):
        [p] = problems("yap(x)\nx = 1\n")
        self.assertEqual(p.code, "SL101")
        self.assertIn("before it gets a value", p.message)

    def test_loop_carried_value_is_fine(self):
        self.assertEqual(problems("""
            doomscroll i in range(3):
                fr i:
                    yap(prev)
                prev = i
        """), [])

    def test_blueprint_used_inside_its_own_body(self):
        [p] = problems("""
            blueprint Node:
                cook f(mee, x=Node):
                    serve x
        """)
        self.assertIn("own blueprint body", p.message)

    def test_blueprint_name_in_method_and_annotation(self):
        self.assertEqual(problems("""
            blueprint Node:
                cook clone(mee, other: Node = ghosted) -> Node:
                    serve Node()
        """), [])

    def test_comprehension_variable_does_not_leak(self):
        self.assertEqual(codes("xs = [y doomscroll y in [1, 2] fr y]\nyap(y)\n"), [("SL101", 2)])

    def test_nested_comprehensions(self):
        self.assertEqual(problems("""
            grid = [[r * c doomscroll c in range(r)] doomscroll r in range(3)]
            d = {k: v doomscroll k, v in {"a": 1}.items()}
            g = (a + b doomscroll a in range(3) doomscroll b in range(a))
        """), [])

    def test_class_scope_not_visible_in_methods(self):
        [p] = problems("""
            blueprint Squad:
                size = 3
                cook big(mee):
                    serve size > 2
        """)
        self.assertEqual((p.code, p.line), ("SL101", 5))

    def test_class_scope_not_visible_in_comprehension_body(self):
        self.assertEqual(codes("""
            blueprint A:
                allowed = [1, 2]
                first_iter_ok = [x doomscroll x in allowed]
                body_bad = [x doomscroll x in range(3) fr x in allowed]
                lam = nohead: allowed
        """), [("SL101", 5), ("SL101", 6)])

    def test_viral(self):
        self.assertEqual(problems("""
            cook setup():
                viral config
                config = {"mood": "ate"}

            setup()
            yap(config)
        """), [])

    def test_viral_without_value_anywhere(self):
        self.assertEqual(codes("cook f():\n    viral ghost_town\n    serve ghost_town\n"),
                         [("SL101", 3)])

    def test_mutuals(self):
        self.assertEqual(problems("""
            cook counter():
                count = 0
                cook bump():
                    mutuals count
                    count += 1
                    serve count
                serve bump
        """), [])

    def test_nested_cook_sees_outer_locals(self):
        self.assertEqual(codes("""
            cook outer():
                x = 1
                cook inner():
                    serve x + z
                serve inner
        """), [("SL101", 5)])

    def test_match_captures(self):
        self.assertEqual(problems("""
            cook react(result):
                spill result:
                    pov {"mood": "ate"}:
                        serve "slay"
                    pov {"mood": mood, **rest}:
                        serve mood, rest
                    pov [first, *others]:
                        serve first, others
                    pov Point(x=0) aka p:
                        serve p
                    pov _:
                        serve ghosted

            blueprint Point:
                chill
        """), [])

    def test_fumble_aka_name(self):
        self.assertEqual(problems("""
            shoot:
                yap(1 / 0)
            fumble ZeroDivisionError aka e:
                yap("L:", e)
        """), [])

    def test_walrus(self):
        self.assertEqual(problems("""
            fr (n := howlongisit([1, 2])) > 1:
                yap(n)
            hits = [m doomscroll x in range(3) fr (m := x * 2)]
            yap(m)
        """), [])

    def test_star_import_turns_off_undefined_names(self):
        self.assertEqual(problems("outta os.path pullup *\nyap(join('a', 'b'), whatever)\n"), [])

    def test_cancel(self):
        self.assertEqual(codes("x = 1\ncancel x\ncancel y\n"), [("SL101", 3)])

    def test_name_probe_in_shoot(self):
        self.assertEqual(problems("""
            shoot:
                has_key
            fumble NameError:
                has_key = ghosted
        """), [])

    def test_string_annotations_and_type_checking_imports(self):
        self.assertEqual(problems("""
            outta typing pullup TYPE_CHECKING
            fr TYPE_CHECKING:
                outta decimal pullup Decimal

            cook f(x: "Decimal") -> "Later":
                serve x

            blueprint Later:
                chill
        """), [])

    def test_all_with_missing_name(self):
        self.assertEqual(codes("pullup os\n__all__ = ['os', 'nope']\n"), [("SL101", 2)])

    def test_slaython_syntax_features(self):
        self.assertEqual(problems("""
            gang Mood: ATE, MID

            lore Post:
                caption: str
                likes: int = 0

                cook big(mee) -> bool:
                    serve mee.likes > 10

            deadass LIMIT = 3

            maincharacter:
                feed = [Post("a")]
                shoot 3:
                    size = feed |> howlongisit
                fumble ValueError:
                    size = 0
                yap(size, Mood.ATE, LIMIT)
                speedrun "rank":
                    yap(feed |> tierlist(key=nohead p: p.likes))
                runitfoo 2:
                    yap("slay")
                idc KeyError:
                    yap({}["k"])

            vibecheck "it works":
                ongod nocap

            lowkeysus(1)
            bedrot(0)
            yap(headzortailz(), pickone([1]))
        """), [])

    def test_slang_in_fstring(self):
        self.assertEqual(problems('name = "a"\nyap(f"{name} {howlongisit(name)} {ghosted}")\n'), [])


class UnusedImports(unittest.TestCase):
    def test_unused(self):
        found = problems("""
            pullup os
            pullup sys
            outta json pullup dumps aka d, loads
            yap(sys.argv, loads)
        """)
        self.assertEqual([(p.code, p.line) for p in found], [("SL102", 2), ("SL102", 4)])
        self.assertEqual(found[0].message, "pullup os, but os never gets used")
        self.assertIn("outta json pullup dumps aka d", found[1].message)

    def test_used_in_function_defined_before_or_after(self):
        self.assertEqual(problems("""
            cook f():
                serve json.dumps(1)
            pullup json
        """), [])

    def test_dotted_import(self):
        self.assertEqual(problems("pullup os.path\nyap(os.path.join('a'))\n"), [])

    def test_used_in_annotation(self):
        self.assertEqual(problems("""
            outta typing pullup List
            items: List[int] = []
        """), [])

    def test_exported(self):
        self.assertEqual(problems("outta os pullup path\n__all__ = ['path']\n"), [])
        self.assertEqual(problems("outta os pullup path aka path\n"), [])

    def test_init_file_reexports(self):
        self.assertEqual(problems("outta .ranking pullup rank\n", "pkg/__init__.slay"), [])

    def test_fallback_imports(self):
        self.assertEqual(problems("""
            shoot:
                pullup ujson aka json
            fumble ImportError:
                pullup json
        """), [])

    def test_future(self):
        self.assertEqual(problems("outta __future__ pullup annotations\n"), [])

    def test_inside_function(self):
        self.assertEqual(codes("""
            cook f():
                pullup os
                pullup sys
                serve sys.argv
        """), [("SL102", 3)])


class UnusedLocals(unittest.TestCase):
    def test_unused(self):
        found = problems("""
            cook f():
                x = 1
                _private = 2
                a, b = 1, 2
                doomscroll i in range(3):
                    chill
                linkup open("f") aka fh:
                    chill
                serve ghosted
        """)
        self.assertEqual([(p.code, p.line) for p in found], [("SL103", 3)])
        self.assertEqual(found[0].message, "x gets a value but is never used")

    def test_module_level_is_not_checked(self):
        self.assertEqual(problems("x = 1\n"), [])

    def test_unused_fumble_name(self):
        [p] = problems("""
            cook f():
                shoot:
                    serve 1
                fumble ValueError aka e:
                    serve 2
        """)
        self.assertEqual((p.code, p.line, p.col), ("SL103", 5, 27))
        self.assertIn("drop the `aka e`", p.message)

    def test_used_by_closure_or_locals(self):
        self.assertEqual(problems("""
            cook a():
                x = 1
                cook b():
                    serve x
                serve b

            cook c():
                y = 1
                serve locals()

            cook d():
                n = 0
                n += 1
        """), [])

    def test_shoot_retry_inside_function(self):
        self.assertEqual(problems("""
            cook f():
                shoot 3:
                    serve 1
                fumble ValueError:
                    serve 2
        """), [])


class Redefinition(unittest.TestCase):
    def test_redefined_unused(self):
        [p] = problems("""
            cook f():
                serve 1

            cook f():
                serve 2
        """)
        self.assertEqual((p.code, p.line), ("SL104", 5))
        self.assertIn("line 2", p.message)

    def test_blueprint(self):
        self.assertEqual(codes("blueprint A:\n    chill\nblueprint A:\n    chill\n"), [("SL104", 3)])

    def test_used_in_between(self):
        self.assertEqual(problems("""
            cook g():
                serve 1
            yap(g())
            cook g():
                serve 2
        """), [])

    def test_used_in_between_by_a_function(self):
        self.assertEqual(problems("""
            cook helper():
                serve 1
            cook main():
                serve helper()
            cook helper():
                serve 2
        """), [])

    def test_branches_and_property(self):
        self.assertEqual(problems("""
            fr nocap:
                cook h():
                    chill
            ornah:
                cook h():
                    chill

            blueprint P:
                @property
                cook x(mee):
                    serve 1

                @x.setter
                cook x(mee, value):
                    chill
        """), [])


class Unreachable(unittest.TestCase):
    def test_after_each_exit(self):
        found = problems("""
            cook f(x):
                serve x
                yap("never")

            doomscroll i in range(3):
                fr i:
                    anyways
                    yap(i)
                dip
                yap(i)

            cook g():
                yeet ValueError()
                yap(1)
        """)
        self.assertEqual([(p.code, p.line) for p in found],
                         [("SL201", 4), ("SL201", 9), ("SL201", 11), ("SL201", 15)])
        self.assertEqual(found[0].message, "this never runs, it comes after serve")
        self.assertIn("after anyways", found[1].message)
        self.assertIn("after dip", found[2].message)
        self.assertIn("after yeet", found[3].message)

    def test_touchgrass(self):
        [p] = problems("touchgrass()\nyap(1)\n")
        self.assertEqual((p.code, p.line), ("SL201", 2))
        self.assertIn("touchgrass()", p.message)

    def test_every_branch_bails(self):
        self.assertEqual(codes("""
            cook h(x):
                fr x:
                    serve 1
                ornah:
                    serve 2
                yap(3)
        """), [("SL201", 7)])

    def test_reachable(self):
        self.assertEqual(problems("""
            cook h(x):
                fr x:
                    serve 1
                yap(2)
                serve 3

            cook empty_gen():
                serve
                drop
        """), [])


class LiteralChecks(unittest.TestCase):
    def test_literally_with_literal(self):
        found = problems("""
            x = 3
            fr x literally "text":
                chill
            fr x literally 3:
                chill
            fr x literally nah -1:
                chill
        """)
        self.assertEqual([(p.code, p.line) for p in found],
                         [("SL301", 3), ("SL301", 5), ("SL301", 7)])
        self.assertIn("use == to compare with 'text'", found[0].message)
        self.assertIn("`literally nah`", found[2].message)
        self.assertIn("use !=", found[2].message)

    def test_literally_with_singletons_is_fine(self):
        self.assertEqual(problems("""
            x = 3
            fr x literally ghosted orr x literally nocap orr x literally nah cap:
                chill
        """), [])

    def test_eq_ghosted(self):
        found = problems("x = 1\nfr x == ghosted:\n    chill\nfr ghosted != x:\n    chill\n")
        self.assertEqual([(p.code, p.line) for p in found], [("SL302", 2), ("SL302", 4)])
        self.assertEqual(found[0].message, "use `literally ghosted` instead of `== ghosted`")
        self.assertEqual(found[1].message, "use `literally nah ghosted` instead of `!= ghosted`")

    def test_ongod_tuple(self):
        self.assertEqual(codes('ongod (1 == 2, "nope")\nongod 1 == 1, "fine"\n'), [("SL305", 1)])

    def test_duplicate_dict_key(self):
        self.assertEqual(codes("d = {'a': 1, 'b': 2, 'a': 3}\ne = {1: 1, '1': 2}\n"), [("SL306", 1)])

    def test_yeet_not_implemented(self):
        self.assertEqual(codes("cook f():\n    yeet NotImplemented\ncook g():\n    yeet NotImplementedError\n"),
                         [("SL307", 2)])


class Fumble(unittest.TestCase):
    def test_swallowers(self):
        found = problems("""
            shoot:
                yap(1)
            fumble:
                chill
            shoot:
                yap(1)
            fumble skillissue:
                chill
            shoot:
                yap(1)
            fumble BaseException:
                chill
        """)
        self.assertEqual([(p.code, p.line, p.col) for p in found],
                         [("SL303", 4, 1), ("SL303", 8, 1), ("SL303", 12, 1)])
        self.assertIn("bare `fumble:`", found[0].message)
        self.assertIn("`fumble skillissue`", found[1].message)

    def test_fine_fumbles(self):
        self.assertEqual(problems("""
            shoot:
                yap(1)
            fumble ValueError:
                chill
            shoot:
                yap(1)
            fumble skillissue aka e:
                yap(e)
        """), [])


class Functions(unittest.TestCase):
    def test_mutable_defaults(self):
        found = problems("""
            cook f(x=[], y={}, z=ghosted, *, w=set()):
                serve x, y, z, w
            g = nohead a=[]: a
        """)
        self.assertEqual([(p.code, p.line) for p in found], [("SL304", 2)] * 3 + [("SL304", 4)])
        self.assertIn("x=[]", found[0].message)
        self.assertIn("default to ghosted", found[0].message)

    def test_immutable_defaults(self):
        self.assertEqual(problems("cook f(x=(), y=ghosted, z=frozenset()):\n    serve x, y, z\n"), [])

    def test_method_without_mee(self):
        found = problems("""
            blueprint Dog:
                cook __init__(mee, name):
                    mee.name = name

                cook bark():
                    yap("woof")

                @staticmethod
                cook fine():
                    chill
        """)
        self.assertEqual([(p.code, p.line) for p in found], [("SL308", 6)])
        self.assertIn("add mee", found[0].message)

    def test_namespace_blueprint(self):
        self.assertEqual(problems("""
            blueprint Tools:
                cook one():
                    serve 1
            yap(Tools.one())
        """), [])


class Errors(unittest.TestCase):
    def test_syntax_error(self):
        [p] = problems("fr x\n    yap(1)\n")
        self.assertEqual((p.code, p.line, p.col), ("SL001", 1, 5))

    def test_compile_error_in_slang(self):
        [p] = problems("serve 3\n")
        self.assertEqual(p.code, "SL001")
        self.assertIn("'return' is 'serve' in Slaython", p.message)

    def test_translator_error(self):
        [p] = problems("deadass X = 1\nX = 2\n")
        self.assertEqual((p.code, p.line), ("SL001", 2))


class Ignores(unittest.TestCase):
    def test_ignore_comments(self):
        found = problems("""
            yap(a)  # lint: ignore
            yap(b)  # lint: ignore[SL102]
            yap(c)  # lint: ignore[SL102, SL101]
            yap(d)
        """)
        self.assertEqual([p.line for p in found], [3, 5])

    def test_select_and_ignore(self):
        src = "pullup os\nyap(nope)\n"
        self.assertEqual([p.code for p in problems(src, select=["SL101"])], ["SL101"])
        self.assertEqual([p.code for p in problems(src, select=["SL1"])], ["SL102", "SL101"])
        self.assertEqual([p.code for p in problems(src, ignore=["SL101"])], ["SL102"])


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_clean(self):
        self.write("ok.slay", "yap(1)\n")
        code, out, _ = run_main(self.dir)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "all clean, no cap")

    def test_problems_and_summary(self):
        a = self.write("a.slay", "pullup os\nyap(nope)\n")
        self.write("sub/b.slay", "serve\n")
        self.write("sub/c.slay", "yap(1)\n")
        self.write(".hidden/d.slay", "yap(nope)\n")
        self.write("__pycache__/e.slay", "yap(nope)\n")
        code, out, _ = run_main(self.dir)
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(lines[0], f"{a}:1:8: SL102 pullup os, but os never gets used")
        self.assertIn("SL001", lines[2])
        self.assertEqual(lines[-1], "3 problems in 2 files")

    def test_select_ignore_flags(self):
        path = self.write("a.slay", "pullup os\nyap(nope)\n")
        code, out, _ = run_main("--select", "SL101", path)
        self.assertEqual((code, out.splitlines()[-1]), (1, "1 problem in 1 file"))
        code, out, _ = run_main("--ignore", "SL101,SL102", path)
        self.assertEqual((code, out.strip()), (0, "all clean, no cap"))

    def test_usage_errors(self):
        self.assertEqual(run_main(os.path.join(self.dir, "missing.slay"))[0], 2)
        self.assertEqual(run_main("--select", "SL999", self.dir)[0], 2)
        self.assertEqual(run_main("--nope")[0], 2)

    def test_codes(self):
        code, out, _ = run_main("--codes")
        self.assertEqual(code, 0)
        self.assertIn("SL201", out)

    def test_module_entry_point(self):
        path = self.write("a.slay", "yap(nope)\n")
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, "-m", "slaython.lint", path], capture_output=True,
                              text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("SL101 who is nope?", proc.stdout)


class Examples(unittest.TestCase):
    # extras.slay has code after touchgrass() on purpose (a real SL201)
    KNOWN = {("extras.slay", 37, "SL201")}

    def test_examples_have_no_false_positives(self):
        found = set()
        for path in lint.slay_files([EXAMPLES]):
            for p in lint.lint_file(path):
                found.add((os.path.basename(p.path), p.line, p.code))
        self.assertLessEqual(found, self.KNOWN)


if __name__ == "__main__":
    unittest.main()
