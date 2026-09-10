#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# tests/test_cli.py: Tests for cli.py
#
#  Description:
#  This test suite covers the command line entry point. It checks how a
#  memo is read from --text or from --input and that an empty or blank
#  source is refused before a request is spent, how the --model and
#  --timeout overrides reach the generation call, and which exit code
#  each outcome produces: 0 for a draft, 1 for a refused setting or a
#  failed generation, and 2 for a command line argparse rejects.
#
#  No request is made. Generation entry points or their request boundary
#  are replaced by stubs, so the suite needs no token, no .env and no
#  endpoint.
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
#      python -m unittest tests.test_cli
#
#  Test Cases:
#    - Read the memo given on the command line with --text.
#    - Refuse an empty --text, which was previously read as no --text at all.
#    - Refuse a --text holding whitespace only.
#    - Read the memo from the file named by --input.
#    - Refuse a file whose content is empty.
#    - Generate a draft and report success with exit status 0.
#    - Apply the --model override to the configuration handed to the core.
#    - Apply the --timeout override to the configuration handed to the core.
#    - Refuse a --timeout that is not positive without spending a request.
#    - Refuse a non-finite --timeout without spending a request.
#    - Refuse a whitespace-only --model without spending a request.
#    - Apply a --model override trimmed of surrounding whitespace.
#    - Refuse an empty memo without spending a request.
#    - Report a generation failure as a failed run.
#    - Name the failure class and its user message in the log.
#    - Refuse a configuration that cannot address an endpoint.
#    - Require a subcommand, which argparse rejects with exit status 2.
#    - Refuse --text and --input given at once.
#    - Refuse a --timeout that is not a number.
#    - Require a body for the titles command.
#    - Run the titles command with a settled body.
#    - Refuse an empty or whitespace-only body file before a request is spent.
#    - Refuse a memo file that is not valid UTF-8 without spending a request.
#    - Refuse a body file that is not valid UTF-8 without spending a request.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v1.3 2026-09-10
#       Cover non-UTF-8 memo and body file refusal before generation.
#  v1.2 2026-09-07
#       Cover title-only body validation and the valid titles command.
#  v1.1 2026-09-06
#       Cover the refusal of a non-finite --timeout and a whitespace-only --model.
#  v1.0 2026-08-05
#       Initial release.
#
########################################################################

import io
import sys
import tempfile
import unittest
from pathlib import Path
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

    def test_refuses_a_non_finite_timeout(self):
        # argparse converts "nan" and "inf" to a float without complaint;
        # only the finite check catches what a bare positivity check does
        # not, so a non-finite override reached the SDK before it existed.
        for value in ("nan", "inf"):
            status, stub = self.run_cli("generate", "--text", "a memo",
                                        "--timeout", value)

            self.assertEqual(1, status)
            stub.assert_not_called()

        # "-inf" is joined with "=": a value starting with "-" that argparse
        # cannot read as a negative number is otherwise mistaken for another
        # option, which is an argparse limitation this change does not touch.
        status, stub = self.run_cli("generate", "--text", "a memo",
                                    "--timeout=-inf")

        self.assertEqual(1, status)
        stub.assert_not_called()

    def test_refuses_a_whitespace_only_model(self):
        status, stub = self.run_cli("generate", "--text", "a memo",
                                    "--model", "   ")

        self.assertEqual(1, status)
        stub.assert_not_called()

    def test_trims_surrounding_whitespace_from_the_model_override(self):
        status, stub = self.run_cli("generate", "--text", "a memo",
                                    "--model", "  another-model  ")

        self.assertEqual(0, status)
        self.assertEqual("another-model", stub.call_args[0][1].generation_model)

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

    def test_runs_the_titles_command_with_a_settled_body(self):
        titles = mock.Mock(return_value=draft())
        with mock.patch.dict("os.environ", ENVIRONMENT, clear=True):
            with mock.patch.object(
                    sys, "argv",
                    ["cli.py", "titles", "--text", "a memo",
                     "--body", "body.md"]):
                with mock.patch("builtins.open",
                                mock.mock_open(read_data="The settled body")):
                    with mock.patch.object(cli, "regenerate_titles", titles):
                        with mock.patch("builtins.print"):
                            status = cli.main()

        self.assertEqual(0, status)
        self.assertEqual("a memo", titles.call_args[0][0])
        self.assertEqual("The settled body", titles.call_args[0][1])

    def test_refuses_a_blank_body_file_without_spending_a_request(self):
        for body in ("", "   \n"):
            with self.subTest(body=repr(body)):
                with mock.patch.dict("os.environ", ENVIRONMENT, clear=True):
                    with mock.patch.object(
                            sys, "argv",
                            ["cli.py", "titles", "--text", "a memo",
                             "--body", "body.md"]):
                        with mock.patch(
                                "builtins.open",
                                mock.mock_open(read_data=body)):
                            with mock.patch(
                                    "sizu_writer.generator.build_titles_messages"
                                    ) as messages:
                                with mock.patch(
                                        "sizu_writer.generator._complete"
                                        ) as complete:
                                    with self.assertLogs(
                                            "cli", level="ERROR") as recorded:
                                        status = cli.main()

                self.assertEqual(1, status)
                messages.assert_not_called()
                complete.assert_not_called()
                self.assertIn(
                    "There is no post body to regenerate titles for.",
                    "\n".join(recorded.output))

    def test_refuses_a_non_utf8_memo_file_without_spending_a_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "memo.txt")
            path.write_bytes(b"\xff")

            with self.assertLogs("cli", level="ERROR") as recorded:
                status, stub = self.run_cli(
                    "generate", "--input", str(path))

        self.assertEqual(1, status)
        stub.assert_not_called()
        line = "\n".join(recorded.output)
        self.assertIn("not valid UTF-8", line)
        self.assertNotIn("0xff", line)

    def test_refuses_a_non_utf8_body_file_without_spending_a_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "body.md")
            path.write_bytes(b"\xff")

            titles = mock.Mock(return_value=draft())
            with mock.patch.dict("os.environ", ENVIRONMENT, clear=True):
                with mock.patch.object(
                        sys, "argv",
                        ["cli.py", "titles", "--text", "a memo",
                         "--body", str(path)]):
                    with mock.patch.object(cli, "regenerate_titles", titles):
                        with self.assertLogs("cli", level="ERROR") as recorded:
                            status = cli.main()

        self.assertEqual(1, status)
        titles.assert_not_called()
        line = "\n".join(recorded.output)
        self.assertIn("not valid UTF-8", line)
        self.assertNotIn("0xff", line)


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
