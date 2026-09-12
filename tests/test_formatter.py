#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# tests/test_formatter.py: Tests for sizu_writer/formatter.py
#
#  Description:
#  This test suite covers the post processing applied to a generated
#  body. It checks the three rewrites the formatter is allowed to make
#  on its own, namely removing an outer code fence, demoting a level one
#  heading and collapsing runs of blank lines, and it checks that a code
#  block belonging to the body survives all three. It also checks that
#  boilerplate is reported as a notice instead of being edited away,
#  which is the line this module draws between formatting and meaning.
#
#  Author: id774 (More info: https://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Running the tests:
#  Run the whole suite from the repository root:
#      python -m unittest discover -s tests
#  Run this module alone:
#      python -m unittest tests.test_formatter
#
#  Test Cases:
#    - Remove a code fence that wraps the whole answer.
#    - Keep a code block that belongs to the body untouched.
#    - Demote a level one heading and report the adjustment as a notice.
#    - Collapse a run of blank lines into a single blank line.
#    - Report boilerplate as a notice without rewriting the body.
#    - Preserve repeated blank lines inside a fenced code block.
#    - Preserve headings inside tilde fenced code blocks.
#    - Keep opposite fence markers from closing the current block.
#    - Remove a tilde fence wrapping the whole answer.
#    - Demote a level-one ATX heading with leading spaces, a tab separator or
#      an empty heading.
#    - Keep a four-space indented hash line, which is indented code, untouched.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v1.3 2026-09-12
#       Cover level-one ATX heading indentation and separator boundaries.
#  v1.2 2026-09-09
#       Cover literal content inside backtick and tilde code fences.
#  v1.1 2026-08-11
#       Cover separate code blocks at the boundaries of a body.
#  v1.0 2026-08-05
#       Initial release.
#
########################################################################

import unittest

from sizu_writer.formatter import normalize_body


class NormalizeBodyTest(unittest.TestCase):

    def test_removes_the_fence_wrapping_the_whole_answer(self):
        body, notices = normalize_body("```markdown\n本文です。\n```")

        self.assertEqual("本文です。", body)
        self.assertEqual([], notices)

    def test_keeps_a_code_block_inside_the_body(self):
        source = "前置きです。\n\n```sh\n# comment\nls\n```\n\n続きです。"

        body, notices = normalize_body(source)

        self.assertEqual(source, body)
        self.assertEqual([], notices)

    def test_keeps_separate_code_blocks_at_the_body_boundaries(self):
        source = ("```python\nprint('first')\n```\n\n本文です。\n\n"
                  "```python\nprint('second')\n```")

        body, notices = normalize_body(source)

        self.assertEqual(source, body)
        self.assertEqual([], notices)

    def test_demotes_a_level_one_heading_and_says_so(self):
        body, notices = normalize_body("# 見出し\n\n本文です。")

        self.assertEqual("## 見出し\n\n本文です。", body)
        self.assertEqual(["The heading level of the body was adjusted."], notices)

    def test_collapses_runs_of_blank_lines(self):
        body, _ = normalize_body("一段落目。\n\n\n\n二段落目。")

        self.assertEqual("一段落目。\n\n二段落目。", body)

    def test_reports_boilerplate_without_rewriting_it(self):
        source = "本文です。いかがだったでしょうか。"

        body, notices = normalize_body(source)

        self.assertEqual(source, body)
        self.assertIn("The body may contain a formulaic opening or closing.", notices)

    def test_preserves_blank_lines_inside_a_backtick_fence(self):
        source = (
            "前置きです。\n\n\n\n"
            "```text\n"
            "line one\n\n\n\n"
            "line two\n"
            "```\n\n\n\n"
            "続きです。"
        )

        body, notices = normalize_body(source)

        expected = (
            "前置きです。\n\n"
            "```text\n"
            "line one\n\n\n\n"
            "line two\n"
            "```\n\n"
            "続きです。"
        )
        self.assertEqual(expected, body)
        self.assertEqual([], notices)

    def test_preserves_a_heading_inside_a_tilde_fence(self):
        source = (
            "前置きです。\n\n"
            "~~~sh\n"
            "# literal comment\n"
            "printf '%s\\n' value\n"
            "~~~\n\n"
            "# 外側の見出し"
        )

        body, notices = normalize_body(source)

        expected = (
            "前置きです。\n\n"
            "~~~sh\n"
            "# literal comment\n"
            "printf '%s\\n' value\n"
            "~~~\n\n"
            "## 外側の見出し"
        )
        self.assertEqual(expected, body)
        self.assertEqual(["The heading level of the body was adjusted."], notices)

    def test_opposite_marker_does_not_close_a_fence(self):
        source = (
            "```text\n"
            "~~~\n"
            "# literal\n"
            "~~~\n"
            "```\n\n"
            "# outside"
        )

        body, notices = normalize_body(source)

        expected = (
            "```text\n"
            "~~~\n"
            "# literal\n"
            "~~~\n"
            "```\n\n"
            "## outside"
        )
        self.assertEqual(expected, body)
        self.assertEqual(["The heading level of the body was adjusted."], notices)

    def test_removes_a_tilde_fence_wrapping_the_whole_answer(self):
        body, notices = normalize_body("~~~markdown\n本文です。\n~~~")

        self.assertEqual("本文です。", body)
        self.assertEqual([], notices)

    def test_demotes_level_one_atx_heading_forms(self):
        cases = [
            ("   # 見出し", "   ## 見出し"),
            ("#\t見出し", "##\t見出し"),
            ("#", "##"),
        ]
        for heading, demoted_heading in cases:
            with self.subTest(heading=repr(heading)):
                source = "前置きです。\n" + heading
                expected = "前置きです。\n" + demoted_heading

                body, notices = normalize_body(source)

                self.assertEqual(expected, body)
                self.assertEqual(
                    ["The heading level of the body was adjusted."], notices)

    def test_does_not_demote_a_four_space_indented_hash_line(self):
        source = "前置きです。\n    # literal"

        body, notices = normalize_body(source)

        self.assertEqual(source, body)
        self.assertEqual([], notices)


if __name__ == "__main__":
    unittest.main()
