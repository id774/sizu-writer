#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# cli.py: Command line entry point of sizu-writer
#
#  Description:
#  This script calls the same generation core as the web application,
#  without starting Flask. It exists so that the prompts can be adjusted
#  and an endpoint verified from a terminal, which is where the quality
#  of the output is settled before any screen is involved.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Usage:
#      python cli.py generate --text "MEMO" [--json]
#      python cli.py generate --input memo.txt [--model NAME] [--json]
#      python cli.py titles --input memo.txt --body draft.md [--json]
#      python cli.py -h | --help
#      python cli.py -v | --version
#
#  Options:
#  - generate
#      Generate a post body and its title candidates.
#  - titles
#      Generate title candidates for a body that already exists.
#  - --text TEXT / --input FILE
#      Source memo, given directly or read from a file.
#  - --body FILE
#      Body handed to the titles command.
#  - --model NAME / --prompt-dir DIR / --timeout SECONDS
#      Override the matching setting for this invocation. --timeout is
#      held to the rule GENERATION_TIMEOUT follows, a number greater
#      than zero. The API token and the base URL have no option on
#      purpose: a command line is readable by every user of the host
#      through ps, and the token is a secret while the endpoint is a
#      decision of the deployment.
#  - --json
#      Print the draft as JSON instead of as text.
#
#  Exit Codes:
#  - 0: The draft was generated and printed. Also what -h and -v return.
#  - 1: The command failed: a setting or an option was refused, the
#       generation settings cannot address an endpoint, the memo could
#       not be read or was empty, or the endpoint did not return a
#       usable draft.
#  - 2: The command line was rejected by argparse, for example an
#       unknown option, a missing subcommand, or --timeout given
#       something that is not a number.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - openai
#
#  Version History:
#  v1.0 2026-08-05
#       Validate the generation settings before a subcommand runs, point
#       --model and --timeout at the GENERATION_* settings, and refuse an
#       empty memo and a --timeout that is not positive before a request
#       is spent. --version still needs no credentials.
#  v0.1 2026-08-04
#       Initial version.
#
########################################################################

import argparse
import dataclasses
import json
import logging
import sys

from config import ConfigError, load_config, validate_generation_config
from sizu_writer import Draft, __version__
from sizu_writer.errors import EmptyInputError, SizuWriterError
from sizu_writer.generator import generate_draft, regenerate_titles

logger = logging.getLogger("cli")


def build_parser() -> argparse.ArgumentParser:
    """ Describe the commands and the options they accept. """
    parser = argparse.ArgumentParser(description="Generate a post draft from a short memo.")
    parser.add_argument("-v", "--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("generate", "titles"):
        command = commands.add_parser(name)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--text")
        source.add_argument("--input")
        command.add_argument("--model")
        command.add_argument("--prompt-dir")
        command.add_argument("--timeout", type=float)
        command.add_argument("--json", action="store_true")
        if name == "titles":
            command.add_argument("--body", required=True)

    return parser


def read_source(arguments: argparse.Namespace) -> str:
    """ Return the memo given on the command line or in a file. """
    # Test against None rather than emptiness. An empty --text is a memo
    # that was given and is unusable, not one that was never given, and
    # reading it as the latter left --input at None for open() to fail on.
    if arguments.text is not None:
        text = arguments.text
    else:
        with open(arguments.input, encoding="utf-8") as handle:
            text = handle.read()

    if not text.strip():
        raise EmptyInputError()
    return text


def report(draft: Draft, as_json: bool) -> None:
    """ Print the draft for a human, or as JSON for a pipe. """
    if as_json:
        print(json.dumps(dataclasses.asdict(draft), ensure_ascii=False, indent=2))
        return

    print("# {0}".format(draft.primary_title))
    for title in draft.alternative_titles:
        print("- {0}".format(title))
    print()
    print(draft.body)
    for notice in draft.notices:
        print("\n[notice] {0}".format(notice), file=sys.stderr)


def main() -> int:
    """ Run one command and return its exit status. """
    arguments = build_parser().parse_args()

    # Configured before the settings are read, so that a refused
    # setting is reported in the same format as everything else. The
    # level LOG_LEVEL asks for is applied as soon as it is known.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = load_config()
    except ConfigError as error:
        logger.error("%s", error)
        return 1

    logging.getLogger().setLevel(
        getattr(logging, config.log_level, logging.INFO))

    if arguments.model:
        config.generation_model = arguments.model
    if arguments.prompt_dir:
        config.prompt_dir = arguments.prompt_dir

    # Repeat the check load_config() performs on GENERATION_TIMEOUT. The
    # override lands after it has run, so a value refused there would
    # otherwise reach the SDK through the option instead.
    if arguments.timeout is not None:
        if arguments.timeout <= 0:
            logger.error("--timeout is %s; expected a positive number.",
                         arguments.timeout)
            return 1
        config.generation_timeout = arguments.timeout

    # After the overrides, so that --model can stand in for a missing
    # GENERATION_MODEL, and before the input is read, so that a
    # misconfiguration is reported without spending a request.
    try:
        validate_generation_config(config)
    except ConfigError as error:
        logger.error("%s", error)
        return 1

    try:
        source = read_source(arguments)
        if arguments.command == "titles":
            with open(arguments.body, encoding="utf-8") as handle:
                draft = regenerate_titles(source, handle.read(), config)
        else:
            draft = generate_draft(source, config)
    except SizuWriterError as error:
        # Fall back to user_message. Most of these carry no text of their
        # own, so the name alone reached the terminal and said nothing.
        logger.error("%s: %s", type(error).__name__,
                     str(error) or error.user_message)
        return 1
    except OSError as error:
        logger.error("Cannot read the input: %s", error)
        return 1

    report(draft, arguments.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
