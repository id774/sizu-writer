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
#  Placeholders are {{input}} and {{body}} only, substituted with
#  str.replace() rather than str.format(), so that a brace written in a
#  prompt does not have to be escaped.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only
#
#  Version History:
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

import logging
import os
from typing import Dict, List

from sizu_writer.errors import InternalError

logger = logging.getLogger(__name__)


def load_prompt(name: str, prompt_dir: str) -> str:
    """ Read one prompt file and return its text. """
    path = os.path.join(prompt_dir, name)
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError as error:
        logger.error("Cannot read the prompt file %s: %s", path, error)
        raise InternalError("prompt file missing: {0}".format(path))


def build_body_messages(input_text: str, prompt_dir: str) -> List[Dict[str, str]]:
    """ Build the messages that ask for a body and its titles. """
    system = load_prompt("system.md", prompt_dir)
    user = load_prompt("body_user.md", prompt_dir)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user.replace("{{input}}", input_text)},
    ]


def build_titles_messages(input_text: str, body: str, prompt_dir: str) -> List[Dict[str, str]]:
    """ Build the messages that ask for titles of an existing body. """
    system = load_prompt("titles_system.md", prompt_dir)
    user = load_prompt("titles_user.md", prompt_dir)
    user = user.replace("{{input}}", input_text).replace("{{body}}", body)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
