#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/prompts.py: Prompt loading and message assembly
#
#  Description:
#  The generation policy lives in prompts/*.md, outside the Python
#  package, so that it can be adjusted without reinstalling the code and
#  replaced as a whole by pointing PROMPT_DIR elsewhere. This module
#  reads those files and assembles the message list handed to the API.
#  It performs no API call.
#
#  Placeholders are {{input}}, {{body}} and {{direction}}. Substitution
#  scans the prompt template once, so text inserted from a memo, a
#  settled body or a Direction is carried literally and is never
#  interpreted as another placeholder. A custom PROMPT_DIR that carries
#  no {{direction}} placeholder keeps working unchanged: nothing here
#  requires a prompt file to use every known placeholder.
#
#  Author: id774 (More info: https://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v1.4 2026-09-21
#       Add the optional {{direction}} placeholder and carry prompt-file
#       diagnostics through InternalError without duplicate library logs.
#  v1.3 2026-09-11
#       Distinguish missing prompt files from other read failures.
#  v1.2 2026-09-10
#       Refuse prompt files that cannot be decoded as UTF-8.
#  v1.1 2026-09-08
#       Refuse blank prompt files and preserve replacement text literally.
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

import logging
import os
import re
from typing import Dict, List

from sizu_writer.errors import InternalError

logger = logging.getLogger(__name__)


def load_prompt(name: str, prompt_dir: str) -> str:
    """ Read one usable prompt file and return its text. """
    path = os.path.join(prompt_dir, name)
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
    except UnicodeDecodeError:
        raise InternalError(
            "prompt file is not valid UTF-8: {0}".format(path))
    except FileNotFoundError:
        raise InternalError("prompt file missing: {0}".format(path))
    except OSError:
        raise InternalError("cannot read prompt file: {0}".format(path))

    if not text:
        raise InternalError(
            "prompt file empty or blank: {0}".format(path))

    return text


def _substitute(template: str,
                replacements: Dict[str, str]) -> str:
    """
    Replace placeholders found in the template without rescanning values.

    A replacement value is user data, not another template. Running one
    regular-expression pass over the original template keeps a literal
    {{input}} or {{body}} inside a memo or body untouched.
    """
    if not replacements:
        return template

    pattern = re.compile("|".join(
        re.escape(placeholder) for placeholder in replacements))
    return pattern.sub(
        lambda match: replacements[match.group(0)], template)


def build_body_messages(input_text: str, prompt_dir: str,
                        direction: str = "") -> List[Dict[str, str]]:
    """ Build the messages that ask for a body and its titles. """
    system = load_prompt("system.md", prompt_dir)
    user = load_prompt("body_user.md", prompt_dir)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _substitute(
            user, {"{{input}}": input_text, "{{direction}}": direction})},
    ]


def build_titles_messages(input_text: str, body: str, prompt_dir: str,
                          direction: str = "") -> List[Dict[str, str]]:
    """ Build the messages that ask for titles of an existing body. """
    system = load_prompt("titles_system.md", prompt_dir)
    user = load_prompt("titles_user.md", prompt_dir)
    user = _substitute(
        user,
        {
            "{{input}}": input_text,
            "{{body}}": body,
            "{{direction}}": direction,
        },
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
