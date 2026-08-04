#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

    def test_demotes_a_level_one_heading_and_says_so(self):
        body, notices = normalize_body("# 見出し\n\n本文です。")

        self.assertEqual("## 見出し\n\n本文です。", body)
        self.assertEqual(["本文の見出し階層を調整しました。"], notices)

    def test_collapses_runs_of_blank_lines(self):
        body, _ = normalize_body("一段落目。\n\n\n\n二段落目。")

        self.assertEqual("一段落目。\n\n二段落目。", body)

    def test_reports_boilerplate_without_rewriting_it(self):
        source = "本文です。いかがだったでしょうか。"

        body, notices = normalize_body(source)

        self.assertEqual(source, body)
        self.assertIn("定型的な導入や締めの表現が含まれている可能性があります。", notices)


if __name__ == "__main__":
    unittest.main()
