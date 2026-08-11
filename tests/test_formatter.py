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
#  Author: id774 (More info: http://id774.net)
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
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
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


if __name__ == "__main__":
    unittest.main()
