import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from slaython import learn
from slaython.learn import LESSONS, grade, run_code


def answer(code):
    """Code as the learner types it: the trailing empty line submits it."""
    return code.rstrip("\n") + "\n\n"


class LearnTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.progress_file = os.path.join(tmp.name, "progress.json")
        env = mock.patch.dict(os.environ, {learn.PROGRESS_ENV: self.progress_file})
        env.start()
        self.addCleanup(env.stop)

    def run_learn(self, *argv, stdin="", lessons=None):
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                mock.patch.object(sys, "stdout", out), \
                mock.patch.object(sys, "stderr", io.StringIO()):
            code = learn.main(list(argv), lessons=lessons)
        return code, out.getvalue()

    def progress(self):
        with open(self.progress_file, encoding="utf-8") as f:
            return json.load(f)

    def write_progress(self, done=(), at=None):
        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump({"done": list(done), "at": at}, f)


class Lessons(unittest.TestCase):
    def test_keys_are_unique(self):
        keys = [lesson.key for lesson in LESSONS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_solution_passes_its_own_check(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.key):
                result = run_code(lesson.solution)
                self.assertIsNone(result.error, f"{lesson.key}: {result.error!r}")
                verdict = grade(lesson, lesson.solution, result)
                self.assertTrue(verdict.ok, f"{lesson.key}: {verdict.message}")

    def test_solutions_have_no_blank_lines(self):
        # A blank line submits the answer, so a solution can't contain one.
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.key):
                self.assertNotIn("\n\n", lesson.solution.strip())

    def test_every_example_runs(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.key):
                result = run_code(lesson.example)
                self.assertIsNone(result.error, f"{lesson.key}: {result.error!r}")
                self.assertTrue(result.output.strip())

    def test_empty_answer_fails_every_lesson(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.key):
                self.assertFalse(grade(lesson, "chill\n", run_code("chill\n")).ok)

    def test_plain_python_answer_needs_the_slang(self):
        lesson = LESSONS[0]
        source = 'print("slay")\nprint(True)\n'
        verdict = grade(lesson, source, run_code(source))
        self.assertFalse(verdict.ok)
        self.assertIn("yap", verdict.message)

    def test_wrong_output_reports_expected_and_got(self):
        lesson = LESSONS[0]
        verdict = grade(lesson, 'yap("nope")\n', run_code('yap("nope")\n'))
        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.expected, "slay\nTrue")
        self.assertEqual(verdict.got, "nope")


class RunCode(unittest.TestCase):
    def test_fresh_namespace_each_run(self):
        run_code("leftover = 1\n")
        self.assertNotIn("leftover", run_code("chill\n").namespace)

    def test_captures_output_and_errors(self):
        result = run_code('yap("before")\n1 / 0\n')
        self.assertEqual(result.output, "before\n")
        self.assertIsInstance(result.error, ZeroDivisionError)

    def test_syntax_error(self):
        self.assertIsInstance(run_code("deadass X = 1\nX = 2\n").error, SyntaxError)

    def test_hmu_does_not_read_real_stdin(self):
        with mock.patch.object(sys, "stdin", io.StringIO("secret\n")):
            result = run_code("x = hmu()\n")
            self.assertEqual(sys.stdin.read(), "secret\n")
        self.assertIsInstance(result.error, EOFError)

    @unittest.skipUnless(sys.gettrace() is None, "step limit is off under a tracer")
    def test_infinite_loop_is_stopped(self):
        result = run_code("lockedin nocap:\n    chill\n", limit=10_000)
        self.assertTrue(result.too_long)
        self.assertFalse(grade(LESSONS[0], "", result).ok)


class Session(LearnTestCase):
    def test_solving_a_lesson_advances_and_saves(self):
        code, out = self.run_learn(stdin=answer(LESSONS[0].solution))
        self.assertEqual(code, 0)
        self.assertIn("Lesson 1/", out)
        self.assertIn("Lesson 2/", out)
        saved = self.progress()
        self.assertEqual(saved["done"], [LESSONS[0].key])
        self.assertEqual(saved["at"], LESSONS[1].key)

    def test_wrong_answer_does_not_save(self):
        code, out = self.run_learn(stdin=answer('yap("wrong")'))
        self.assertEqual(code, 0)
        self.assertIn("expected:", out)
        self.assertIn("got:", out)
        self.assertNotIn("Lesson 2/", out)
        self.assertEqual(self.progress()["done"], [])

    def test_error_answer_shows_traceback(self):
        _, out = self.run_learn(stdin=answer("yap(1 / 0)"))
        self.assertIn("ZeroDivisionError", out)
        self.assertEqual(self.progress()["done"], [])

    def test_retry_after_wrong_answer(self):
        stdin = answer('yap("wrong")') + answer(LESSONS[0].solution)
        _, out = self.run_learn(stdin=stdin)
        self.assertIn("Lesson 2/", out)
        self.assertEqual(self.progress()["done"], [LESSONS[0].key])

    def test_hint(self):
        _, out = self.run_learn(stdin="hint\n")
        self.assertIn(LESSONS[0].hint, out)
        self.assertEqual(self.progress()["done"], [])

    def test_solution_shows_but_does_not_complete(self):
        _, out = self.run_learn(stdin="solution\n")
        for line in LESSONS[0].solution.splitlines():
            self.assertIn(line, out)
        self.assertEqual(self.progress()["done"], [])
        self.assertEqual(self.progress()["at"], LESSONS[0].key)

    def test_skip(self):
        _, out = self.run_learn(stdin="skip\n")
        self.assertIn("Lesson 2/", out)
        self.assertEqual(self.progress(), {"version": 1, "done": [], "at": LESSONS[1].key})

    def test_back(self):
        _, out = self.run_learn(stdin="skip\nback\n")
        self.assertEqual(out.count("Lesson 1/"), 2)
        self.assertEqual(self.progress()["at"], LESSONS[0].key)

    def test_back_on_first_lesson(self):
        _, out = self.run_learn(stdin="back\n")
        self.assertIn("first lesson", out)

    def test_quit(self):
        code, out = self.run_learn("2", stdin="quit\n" + answer(LESSONS[1].solution))
        self.assertEqual(code, 0)
        self.assertIn("progress saved", out)
        self.assertNotIn("Lesson 3/", out)
        self.assertEqual(self.progress(), {"version": 1, "done": [], "at": LESSONS[1].key})

    def test_eof_exits_cleanly(self):
        code, out = self.run_learn(stdin="")
        self.assertEqual(code, 0)
        self.assertIn("progress saved", out)

    def test_eof_submits_unfinished_buffer(self):
        _, out = self.run_learn(stdin=LESSONS[0].solution)
        self.assertIn("Lesson 2/", out)

    def test_multiline_bracket_survives_blank_line(self):
        # The blank line is inside an open bracket, so it doesn't submit yet.
        stdin = 'yap("slay")\nyap(\n\nnocap)\n\n'
        _, out = self.run_learn(stdin=stdin)
        self.assertEqual(self.progress()["done"], [LESSONS[0].key])

    def test_resume_where_you_left_off(self):
        self.write_progress(done=[LESSONS[0].key], at=LESSONS[2].key)
        _, out = self.run_learn(stdin="")
        self.assertIn("Lesson 3/", out)
        self.assertNotIn("Lesson 1/", out)

    def test_resume_first_unfinished_without_position(self):
        self.write_progress(done=[LESSONS[0].key, LESSONS[1].key])
        _, out = self.run_learn(stdin="")
        self.assertIn("Lesson 3/", out)

    def test_jump_to_lesson(self):
        _, out = self.run_learn("3", stdin="")
        self.assertIn(f"Lesson 3/{len(LESSONS)}: {LESSONS[2].title}", out)

    def test_jump_out_of_range(self):
        code, _ = self.run_learn(str(len(LESSONS) + 1))
        self.assertEqual(code, 2)
        code, _ = self.run_learn("0")
        self.assertEqual(code, 2)

    def test_unknown_option(self):
        code, _ = self.run_learn("--nope")
        self.assertEqual(code, 2)

    def test_corrupt_progress_file_starts_fresh(self):
        with open(self.progress_file, "w", encoding="utf-8") as f:
            f.write("{not json")
        code, out = self.run_learn(stdin="")
        self.assertEqual(code, 0)
        self.assertIn("Lesson 1/", out)

    def test_whole_course_with_solutions(self):
        stdin = "".join(answer(lesson.solution) for lesson in LESSONS)
        code, out = self.run_learn(stdin=stdin)
        self.assertEqual(code, 0)
        self.assertIn("finished every lesson", out)
        saved = self.progress()
        self.assertEqual(saved["done"], [lesson.key for lesson in LESSONS])
        self.assertIsNone(saved["at"])
        code, out = self.run_learn(stdin="")
        self.assertIn("already finished", out)

    def test_finish_with_skipped_lessons(self):
        self.write_progress(at=LESSONS[-1].key)
        _, out = self.run_learn(stdin=answer(LESSONS[-1].solution))
        self.assertIn("skipped some: 1, 2", out)


class Options(LearnTestCase):
    def test_list(self):
        self.write_progress(done=[LESSONS[0].key], at=LESSONS[1].key)
        code, out = self.run_learn("--list")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("[x]  1."))
        self.assertTrue(lines[1].startswith("[ ]  2."))
        self.assertIn("you are here", lines[1])
        for lesson in LESSONS:
            self.assertIn(lesson.title, out)
        self.assertIn(f"1/{len(LESSONS)} done", out)

    def test_reset(self):
        self.write_progress(done=[LESSONS[0].key])
        code, out = self.run_learn("--reset")
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(self.progress_file))
        code, _ = self.run_learn("--reset")  # nothing to delete is fine too
        self.assertEqual(code, 0)

    def test_help(self):
        code, out = self.run_learn("--help")
        self.assertEqual(code, 0)
        self.assertIn("slaython learn", out)

    def test_no_color_when_piped(self):
        _, out = self.run_learn(stdin="")
        self.assertNotIn("\033[", out)

    def test_custom_lessons(self):
        # Lessons are plain data, so a new one drops straight in.
        extra = learn.Lesson(
            key="extra", title="extra", explanation="x", example='yap("hi")\n',
            task="yap 3", check=learn.passes(lambda out, ns: ns["x"] == 3, "x set to 3"),
            hint="x = 3", solution="x = 3\nyap(x)\n")
        code, out = self.run_learn(stdin=answer("x = 3"), lessons=[extra])
        self.assertEqual(code, 0)
        self.assertIn("finished every lesson", out)
        self.assertEqual(self.progress()["done"], ["extra"])


if __name__ == "__main__":
    unittest.main()
