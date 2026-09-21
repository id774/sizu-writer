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
#    - Refuse a missing prompt file, carrying the diagnostic on the exception
#      without a library log.
#    - Refuse an unreadable prompt file the same way.
#    - Refuse an empty prompt file the same way.
#    - Refuse a whitespace-only prompt file the same way.
#    - Replace template-origin {{input}} without rescanning the memo.
#    - Replace template-origin {{input}} and {{body}} without rescanning
#      either value, keeping an unknown placeholder literal.
#    - Replace template-origin {{direction}} without rescanning the value,
#      defaulting to a blank direction when the caller does not pass one.
#    - Replace {{direction}}, {{input}} and {{body}} together in the title
#      message without rescanning any of the three values.
#    - Refuse a blank prompt before generation reaches the provider.
#    - Refuse a prompt file that is not valid UTF-8, carrying the diagnostic
#      on the exception without a library log.
#    - Refuse a non-UTF-8 prompt before generation reaches the provider.
#    - Keep the required title policy shared by the full and title-only prompts.
#    - Keep the required direction policy shared by the full and title-only prompts.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v1.4 2026-09-21
#       Cover the optional {{direction}} placeholder, its shared policy, and
#       prompt diagnostics carried without library logging.
#  v1.3 2026-09-12
#       Keep the required title policy shared by full and title-only prompts.
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

            with mock.patch.object(prompts.logger, "error") as error_log:
                with self.assertRaises(InternalError) as refused:
                    prompts.load_prompt("system.md", prompt_dir)

        error_log.assert_not_called()
        self.assertIn(path, refused.exception.diagnostic)
        self.assertIn("prompt file missing", refused.exception.diagnostic)
        self.assertNotIn("cannot read prompt file", refused.exception.diagnostic)

    def test_refuses_an_unreadable_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_text("prompt text", encoding="utf-8")

            with mock.patch("builtins.open", side_effect=PermissionError("denied")):
                with mock.patch.object(prompts.logger, "error") as error_log:
                    with self.assertRaises(InternalError) as refused:
                        prompts.load_prompt("system.md", prompt_dir)

        error_log.assert_not_called()
        self.assertIn(path, refused.exception.diagnostic)
        self.assertIn("cannot read prompt file", refused.exception.diagnostic)
        self.assertNotIn("missing", refused.exception.diagnostic)
        self.assertNotIn("denied", refused.exception.diagnostic)

    def test_refuses_an_empty_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_text("", encoding="utf-8")

            with mock.patch.object(prompts.logger, "error") as error_log:
                with self.assertRaises(InternalError) as refused:
                    prompts.load_prompt("system.md", prompt_dir)

        error_log.assert_not_called()
        self.assertIn(path, refused.exception.diagnostic)
        self.assertIn("empty or blank", refused.exception.diagnostic)

    def test_refuses_a_whitespace_only_prompt(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_text("   \n\n", encoding="utf-8")

            with mock.patch.object(prompts.logger, "error") as error_log:
                with self.assertRaises(InternalError) as refused:
                    prompts.load_prompt("system.md", prompt_dir)

        error_log.assert_not_called()
        self.assertIn(path, refused.exception.diagnostic)
        self.assertIn("empty or blank", refused.exception.diagnostic)

    def test_refuses_a_prompt_that_is_not_valid_utf8(self):
        with tempfile.TemporaryDirectory() as prompt_dir:
            path = str(Path(prompt_dir, "system.md"))
            Path(path).write_bytes(b"\xff")

            with mock.patch.object(prompts.logger, "error") as error_log:
                with self.assertRaises(InternalError) as refused:
                    prompts.load_prompt("system.md", prompt_dir)

        error_log.assert_not_called()
        self.assertIn(path, refused.exception.diagnostic)
        self.assertIn("not valid UTF-8", refused.exception.diagnostic)
        self.assertNotIn("0xff", refused.exception.diagnostic)


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

    def test_defaults_to_a_blank_direction(self):
        texts = {
            "system.md": "system",
            "body_user.md": "Direction: {{direction}}\nMemo: {{input}}",
        }

        with mock.patch.object(prompts, "load_prompt",
                               side_effect=lambda name, prompt_dir: texts[name]):
            messages = prompts.build_body_messages("a memo", "prompts")

        self.assertEqual("Direction: \nMemo: a memo", messages[1]["content"])

    def test_replaces_template_origin_direction_without_rescanning_it(self):
        texts = {
            "system.md": "system",
            "body_user.md": ("Direction one: {{direction}}\n"
                             "Direction two: {{direction}}\n"
                             "Memo: {{input}}"),
        }
        direction = "literal {{input}} / {{body}} / {{direction}}"
        expected_user = (
            "Direction one: literal {{input}} / {{body}} / {{direction}}\n"
            "Direction two: literal {{input}} / {{body}} / {{direction}}\n"
            "Memo: a memo")

        with mock.patch.object(prompts, "load_prompt",
                               side_effect=lambda name, prompt_dir: texts[name]):
            messages = prompts.build_body_messages("a memo", "prompts", direction)

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

    def test_defaults_to_a_blank_direction(self):
        texts = {
            "titles_system.md": "titles system",
            "titles_user.md": "Direction: {{direction}}\nMemo: {{input}}\nBody: {{body}}",
        }

        with mock.patch.object(prompts, "load_prompt",
                               side_effect=lambda name, prompt_dir: texts[name]):
            messages = prompts.build_titles_messages("a memo", "a body", "prompts")

        self.assertEqual(
            "Direction: \nMemo: a memo\nBody: a body", messages[1]["content"])

    def test_replaces_direction_input_and_body_without_rescanning_any(self):
        texts = {
            "titles_system.md": "titles system",
            "titles_user.md": ("Direction: {{direction}}\n"
                               "Memo: {{input}}\n"
                               "Body: {{body}}"),
        }
        direction = "literal {{input}} / {{body}} / {{direction}}"
        input_text = "memo {{input}} / {{body}} / {{direction}}"
        body = "body {{input}} / {{body}} / {{direction}}"
        expected_user = (
            "Direction: literal {{input}} / {{body}} / {{direction}}\n"
            "Memo: memo {{input}} / {{body}} / {{direction}}\n"
            "Body: body {{input}} / {{body}} / {{direction}}")

        with mock.patch.object(prompts, "load_prompt",
                               side_effect=lambda name, prompt_dir: texts[name]):
            messages = prompts.build_titles_messages(
                input_text, body, "prompts", direction)

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


class SharedTitlePolicyTest(unittest.TestCase):
    """ Keep the full and title-only prompts from drifting apart. """

    def test_full_and_title_only_prompts_share_the_required_title_policy(self):
        repository_root = Path(__file__).resolve().parent.parent
        required_phrases = (
            "the point that was sorted out again",
            "When the matter is unsettled, an observed fact or the point "
            "where the thinking started makes a fine title.",
        )

        for prompt_name in ("system.md", "titles_system.md"):
            text = Path(repository_root, "prompts", prompt_name).read_text(
                encoding="utf-8")
            for phrase in required_phrases:
                with self.subTest(prompt=prompt_name, phrase=phrase):
                    self.assertIn(phrase, text)


class SharedDirectionPolicyTest(unittest.TestCase):
    """ Keep the full and title-only prompts from drifting on direction semantics. """

    def test_full_and_title_only_prompts_share_the_required_direction_policy(self):
        repository_root = Path(__file__).resolve().parent.parent
        required_phrase = (
            "When the direction is blank, no additional instruction was given for "
            "this\nrequest: follow the policy above as it stands, and never remark "
            "in the output\non whether a direction was given or what it said."
        )

        for prompt_name in ("system.md", "titles_system.md"):
            text = Path(repository_root, "prompts", prompt_name).read_text(
                encoding="utf-8")
            with self.subTest(prompt=prompt_name):
                self.assertIn(required_phrase, text)


if __name__ == "__main__":
    unittest.main()
