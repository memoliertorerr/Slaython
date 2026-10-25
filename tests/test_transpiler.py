import sys
import textwrap
import unittest

from slaython import keywords, slayify, slayify_with_report, transpile


def slay(src):
    return transpile(textwrap.dedent(src))


class KeywordTranslation(unittest.TestCase):
    def test_every_single_word_keyword(self):
        for s in keywords.SLANG:
            if s.kind in ("keyword", "builtin"):
                self.assertEqual(transpile(f"x = a {s.slang} b\n"), f"x = a {s.python} b\n", s.slang)

    def test_values(self):
        self.assertEqual(transpile("x = [nocap, cap, ghosted]"), "x = [True, False, None]")

    def test_if_elif_else(self):
        src = """\
        fr a:
            chill
        ornah fr b:
            chill
        ornah:
            chill
        """
        self.assertEqual(slay(src), textwrap.dedent(src)
                         .replace("ornah fr", "elif").replace("fr a", "if a")
                         .replace("ornah", "else").replace("chill", "pass"))

    def test_ternary_else_is_not_elif(self):
        self.assertEqual(transpile("x = 1 fr a ornah 2"), "x = 1 if a else 2")

    def test_ornah_fr_on_separate_lines_stays_separate(self):
        src = "ornah:\n    fr x:\n        chill\n"
        self.assertEqual(transpile(src), "else:\n    if x:\n        pass\n")

    def test_line_numbers_are_kept(self):
        src = "fr x:\n    yap(1)\n\n\nornah:\n    yap('''a\nb''')\n"
        out = transpile(src)
        self.assertEqual(out.count("\n"), src.count("\n"))

    def test_strings_and_comments_untouched(self):
        src = 'yap("no cap fr fr")  # cook serve dip\n'
        self.assertEqual(transpile(src), 'print("no cap fr fr")  # cook serve dip\n')

    def test_attributes_and_keyword_args_untouched(self):
        self.assertEqual(transpile("df.reset_index(drop=nocap)"), "df.reset_index(drop=True)")
        self.assertEqual(transpile("x = obj.cap + obj.yap"), "x = obj.cap + obj.yap")

    def test_slang_inside_longer_names_untouched(self):
        self.assertEqual(transpile("capital = frank + nahh"), "capital = frank + nahh")

    def test_python_keywords_still_work(self):
        src = "def f(x):\n    if x is not None:\n        return [i for i in x]\n"
        self.assertEqual(transpile(src), src)

    def test_imports(self):
        self.assertEqual(transpile("outta os pullup path aka p"), "from os import path as p")
        self.assertEqual(transpile("yeet E() outta err"), "raise E() from err")

    def test_soft_keywords(self):
        src = "spill cmd:\n    pov [x, y]: chill\n    pov _:\n        chill\n"
        self.assertEqual(transpile(src), "match cmd:\n    case [x, y]: pass\n    case _:\n        pass\n")

    def test_soft_keywords_as_plain_names(self):
        for src in ("spill = 3", "spill.x = 1", "pov: int = 3", "yap(spill, pov)", "spill(1)"):
            self.assertEqual(transpile(src), src.replace("yap", "print"))

    @unittest.skipIf(sys.version_info < (3, 12), "f-strings are tokenized as one token before 3.12")
    def test_fstring_expressions(self):
        self.assertEqual(transpile('f"{a fr b ornah c} fr"'), 'f"{a if b else c} fr"')


class Slayify(unittest.TestCase):
    def test_round_trip(self):
        src = textwrap.dedent("""\
            import os as o
            from math import pi
            class A(B):
                def f(self, x=None):
                    if x is not None and x in self:
                        return [i for i in x if not i]
                    elif x:
                        yield x
                    else:
                        raise ValueError() from None
            async def g():
                await h()
                with open(p) as f:
                    pass
            match v:
                case 1:
                    print(super(), input())
            """)
        slang = slayify(src)
        self.assertIn("ornah fr x:", slang)
        self.assertIn("blueprint A(B):", slang)
        self.assertIn("spill v:", slang)
        self.assertEqual(transpile(slang), src)

    def test_python_soft_keyword_names_untouched(self):
        src = "match = re.match(p, s)\ncase = 1\n"
        self.assertEqual(slayify(src), src)

    def test_collisions_reported(self):
        _, clashes = slayify_with_report("drop = 1\nyap(drop)\nx.drop\nf(drop=2)\n")
        self.assertEqual([(c.row, c.name) for c in clashes], [(2, "yap"), (2, "drop")])


class Keywords(unittest.TestCase):
    def test_no_duplicate_slang(self):
        words = [s.slang for s in keywords.SLANG]
        self.assertEqual(len(words), len(set(words)))

    def test_slang_is_not_a_python_keyword(self):
        import keyword
        for word in keywords.ALL_SLANG_WORDS:
            self.assertFalse(keyword.iskeyword(word), word)

    def test_all_hard_keywords_covered(self):
        import keyword
        covered = {s.python for s in keywords.SLANG}
        self.assertEqual(set(keyword.kwlist) - covered, set())


if __name__ == "__main__":
    unittest.main()
