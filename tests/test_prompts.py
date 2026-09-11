#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# tests/test_prompts.py: Tests for sizu_writer/prompts.py
#
#  Description:
#  This suite covers prompt loading and literal placeholder substitution.
#  It refuses a prompt that cannot supply usable text before generation
#  reaches its request boundary, and keeps memo and body text opaque when
#  placeholders are inserted into a prompt template.
#
#  No network or API request is made.
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
#      python -m unittest tests.test_prompts
#
#  Test Cases:
#    - Read and trim a usable prompt file.
#    - Refuse a missing prompt file.
#    - Refuse an unreadable prompt file.
#    - Refuse an empty prompt file.
#    - Refuse a whitespace-only prompt file.
#    - Replace template-origin {{input}} without rescanning the memo.
#    - Replace template-origin {{input}} and {{body}} without rescanning
#      either value, keeping an unknown placeholder literal.
#    - Refuse a blank prompt before generation reaches the provider.
#    - Refuse a prompt file that is not valid UTF-8.
#    - Refuse a non-UTF-8 prompt before generation reaches the provider.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v1.2 2026-09-11
#       Cover distinct diagnostics for missing and unreadable prompt files.
#  v1.1 2026-09-10
#       Cover non-UTF-8 prompt refusal before generation.
#  v1.0 2026-09-08
#       Initial release.
#
########################################################################

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import Config
from sizu_writer import generator, prompts
from sizu_writer.errors import InternalError


class LoadPromptTest(unittest.TestCase):

    def test_reads_and_trims_a_usable_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            Path(prompt_dir, "system.md").write_text(
                "  prompt text\n\n", encoding="utf-8")

            text = prompts.load_prompt("system.md", prompt_dir)

        self.assertEqual("prompt text", text)

    def test_refuses_a_missing_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))

            with self.assertLogs("sizu_writer.prompts", level="ERROR") as recorded:
                with self.assertRaises(InternalError) as refused:
                    prompts.load_prompt("system.md", prompt_dir)

        self.assertIn(path, "\n".join(recorded.output))
        self.assertIn("prompt file missing", str(refused.exception))
        self.assertNotIn("cannot read prompt file", str(refused.exception))

    def test_refuses_an_unreadable_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_text("prompt text", encoding="utf-8")

            with mock.patch("builtins.open", side_effect=PermissionError("denied")):
                with self.assertLogs("sizu_writer.prompts", level="ERROR") as recorded:
                    with self.assertRaises(InternalError) as refused:
                        prompts.load_prompt("system.md", prompt_dir)

        line = "\n".join(recorded.output)
        self.assertIn(path, line)
        self.assertIn("Cannot read the prompt file", line)
        self.assertIn("cannot read prompt file", str(refused.exception))
        self.assertNotIn("missing", str(refused.exception))

    def test_refuses_an_empty_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_text("", encoding="utf-8")

            with self.assertLogs("sizu_writer.prompts", level="ERROR") as recorded:
                with self.assertRaises(InternalError):
                    prompts.load_prompt("system.md", prompt_dir)

        line = "\n".join(recorded.output)
        self.assertIn(path, line)
        self.assertIn("empty or blank", line)

    def test_refuses_a_whitespace_only_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_text("   \n\n", encoding="utf-8")

            with self.assertLogs("sizu_writer.prompts", level="ERROR") as recorded:
                with self.assertRaises(InternalError):
                    prompts.load_prompt("system.md", prompt_dir)

        line = "\n".join(recorded.output)
        self.assertIn(path, line)
        self.assertIn("empty or blank", line)

    def test_refuses_a_prompt_that_is_not_valid_utf8(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_bytes(b"\xff")

            with self.assertLogs(
                    "sizu_writer.prompts", level="ERROR") as recorded:
                with self.assertRaises(InternalError) as refused:
                    prompts.load_prompt("system.md", prompt_dir)

        line = "\n".join(recorded.output)
        self.assertIn(path, line)
        self.assertIn("not valid UTF-8", line)
        self.assertNotIn("0xff", line)
        self.assertIn("not valid UTF-8", str(refused.exception))


class BodyMessagesTest(unittest.TestCase):

    def test_replaces_template_input_without_rescanning_the_memo(self):
        texts = {
            "system.md": "system",
            "body_user.md": ("Memo one: {{input}}\n"
                             "Memo two: {{input}}\n"
                             "Unknown: {{tone}}"),
        }
        input_text = "literal {{input}} / {{body}} / {{tone}}"
        expected_user = ("Memo one: literal {{input}} / {{body}} / {{tone}}\n"
                         "Memo two: literal {{input}} / {{body}} / {{tone}}\n"
                         "Unknown: {{tone}}")

        with mock.patch.object(prompts, "load_prompt",
                               side_effect=lambda name, prompt_dir: texts[name]):
            messages = prompts.build_body_messages(input_text, "prompts")

        self.assertEqual("system", messages[0]["content"])
        self.assertEqual(expected_user, messages[1]["content"])


class TitleMessagesTest(unittest.TestCase):

    def test_replaces_title_placeholders_without_rescanning_values(self):
        texts = {
            "titles_system.md": "titles system",
            "titles_user.md": ("Memo one: {{input}}\n"
                               "Body one: {{body}}\n"
                               "Memo two: {{input}}\n"
                               "Body two: {{body}}\n"
                               "Unknown: {{tone}}"),
        }
        input_text = "memo {{input}} / {{body}} / {{tone}}"
        body = "body {{input}} / {{body}} / {{tone}}"
        expected_user = ("Memo one: memo {{input}} / {{body}} / {{tone}}\n"
                         "Body one: body {{input}} / {{body}} / {{tone}}\n"
                         "Memo two: memo {{input}} / {{body}} / {{tone}}\n"
                         "Body two: body {{input}} / {{body}} / {{tone}}\n"
                         "Unknown: {{tone}}")

        with mock.patch.object(prompts, "load_prompt",
                               side_effect=lambda name, prompt_dir: texts[name]):
            messages = prompts.build_titles_messages(input_text, body, "prompts")

        self.assertEqual("titles system", messages[0]["content"])
        self.assertEqual(expected_user, messages[1]["content"])


class GenerationBoundaryTest(unittest.TestCase):

    def test_refuses_a_blank_prompt_before_the_request_boundary(self):
        for system_text in ("", "   \n"):
            with self.subTest(system_text=repr(system_text)):
                with tempfile.TemporaryDirectory() as prompt_dir:
                    Path(prompt_dir, "body_user.md").write_text(
                        "{{input}}", encoding="utf-8")
                    Path(prompt_dir, "system.md").write_text(
                        system_text, encoding="utf-8")

                    config = Config(prompt_dir=prompt_dir)

                    with mock.patch.object(generator, "_complete") as complete:
                        with self.assertRaises(InternalError):
                            generator.generate_draft("a memo", config)

                complete.assert_not_called()

    def test_refuses_a_non_utf8_prompt_before_the_request_boundary(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            Path(prompt_dir, "system.md").write_bytes(b"\xff")
            Path(prompt_dir, "body_user.md").write_text(
                "{{input}}", encoding="utf-8")
            config = Config(prompt_dir=prompt_dir)

            with mock.patch.object(generator, "_complete") as complete:
                with self.assertRaises(InternalError):
                    generator.generate_draft("a memo", config)

        complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
