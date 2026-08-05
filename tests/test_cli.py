#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import sys
import unittest
from unittest import mock

import cli
from sizu_writer import Draft
from sizu_writer.errors import EmptyInputError, UpstreamTimeoutError

# The four settings validate_generation_config() requires. No request is
# made: generate_draft is replaced by a stub in every test below.
ENVIRONMENT = {
    "GENERATION_BACKEND": "openai-compatible",
    "GENERATION_API_TOKEN": "uuid:secret",
    "GENERATION_BASE_URL": "https://api.ai.sakura.ad.jp/v1",
    "GENERATION_MODEL": "a-model",
}


def draft():
    return Draft(body="The body.", primary_title="The leading title",
                 alternative_titles=["Another candidate"], model="a-model",
                 generated_at="2026-08-05T09:00:00+09:00")


def parse(*arguments):
    return cli.build_parser().parse_args(list(arguments))


def refuse(*arguments):
    """ Return the exit code argparse ends the process with. """
    with mock.patch.object(sys, "stderr", io.StringIO()):
        with mock.patch.object(sys, "stdout", io.StringIO()):
            try:
                parse(*arguments)
            except SystemExit as refused:
                return refused.code
    return 0


class ReadSourceTest(unittest.TestCase):

    def test_reads_the_memo_given_on_the_command_line(self):
        self.assertEqual("a memo", cli.read_source(
            parse("generate", "--text", "a memo")))

    def test_refuses_an_empty_text(self):
        # An empty --text was read as no --text at all, which left --input
        # at None for open() and ended the run in a traceback.
        with self.assertRaises(EmptyInputError):
            cli.read_source(parse("generate", "--text", ""))

    def test_refuses_a_text_of_whitespace_only(self):
        with self.assertRaises(EmptyInputError):
            cli.read_source(parse("generate", "--text", "   \n"))

    def test_reads_the_memo_from_a_file(self):
        with mock.patch("builtins.open",
                        mock.mock_open(read_data="a memo in a file")):
            self.assertEqual("a memo in a file", cli.read_source(
                parse("generate", "--input", "memo.txt")))

    def test_refuses_an_empty_file(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="\n")):
            with self.assertRaises(EmptyInputError):
                cli.read_source(parse("generate", "--input", "memo.txt"))


class MainTest(unittest.TestCase):
    """ Drive main() with the generation core replaced by a stub. """

    def run_cli(self, *arguments, **options):
        stub = mock.Mock(return_value=draft(),
                         side_effect=options.get("failure"))
        with mock.patch.dict("os.environ", ENVIRONMENT, clear=True):
            with mock.patch.object(sys, "argv", ["cli.py"] + list(arguments)):
                with mock.patch.object(cli, "generate_draft", stub):
                    with mock.patch("builtins.print"):
                        return cli.main(), stub

    def test_generates_a_draft_and_reports_success(self):
        status, stub = self.run_cli("generate", "--text", "a memo")

        self.assertEqual(0, status)
        self.assertEqual("a memo", stub.call_args[0][0])

    def test_applies_the_model_override(self):
        status, stub = self.run_cli("generate", "--text", "a memo",
                                    "--model", "another-model")

        self.assertEqual(0, status)
        self.assertEqual("another-model", stub.call_args[0][1].generation_model)

    def test_applies_the_timeout_override(self):
        status, stub = self.run_cli("generate", "--text", "a memo",
                                    "--timeout", "90")

        self.assertEqual(0, status)
        self.assertEqual(90.0, stub.call_args[0][1].generation_timeout)

    def test_refuses_a_timeout_that_is_not_positive(self):
        # load_config() refuses the same value in GENERATION_TIMEOUT. The
        # override is applied after it has run, so without a check of its
        # own the option carried a negative timeout to the SDK.
        for value in ("0", "-5"):
            status, stub = self.run_cli("generate", "--text", "a memo",
                                        "--timeout", value)

            self.assertEqual(1, status)
            stub.assert_not_called()

    def test_refuses_an_empty_memo_without_spending_a_request(self):
        status, stub = self.run_cli("generate", "--text", "")

        self.assertEqual(1, status)
        stub.assert_not_called()

    def test_reports_a_generation_failure_as_a_failed_run(self):
        status, _ = self.run_cli("generate", "--text", "a memo",
                                 failure=UpstreamTimeoutError())

        self.assertEqual(1, status)

    def test_names_the_failure_and_its_message_in_the_log(self):
        with self.assertLogs("cli", level="ERROR") as recorded:
            self.run_cli("generate", "--text", "a memo",
                         failure=UpstreamTimeoutError())

        line = "\n".join(recorded.output)
        self.assertIn("UpstreamTimeoutError", line)
        # These errors carry no text of their own, so without the fallback
        # to user_message the line said the name and nothing more.
        self.assertIn("Generation took too long", line)

    def test_refuses_a_configuration_that_cannot_address_an_endpoint(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch.object(sys, "argv",
                                   ["cli.py", "generate", "--text", "a memo"]):
                with mock.patch.object(cli, "generate_draft") as stub:
                    self.assertEqual(1, cli.main())

        stub.assert_not_called()


class ParserTest(unittest.TestCase):

    def test_requires_a_subcommand(self):
        self.assertEqual(2, refuse())

    def test_refuses_both_sources_at_once(self):
        self.assertEqual(2, refuse("generate", "--text", "a memo",
                                   "--input", "memo.txt"))

    def test_refuses_a_timeout_that_is_not_a_number(self):
        self.assertEqual(2, refuse("generate", "--text", "a memo",
                                   "--timeout", "soon"))

    def test_requires_a_body_for_the_titles_command(self):
        self.assertEqual(2, refuse("titles", "--input", "memo.txt"))


if __name__ == "__main__":
    unittest.main()
