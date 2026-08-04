#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/formatter.py: Post processing of the generated body
#
#  Description:
#  This module turns the model output into a body that can be pasted
#  into the posting form. It rewrites only what can be decided
#  mechanically: an outer code fence, a level one heading, and runs of
#  blank lines. Anything that would touch the meaning of a sentence is
#  reported as a notice instead, and the notices are shown outside the
#  body area so that they can never be copied with it.
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

import re
from typing import List, Tuple

# The phrases are Japanese because the generated post is: they are the
# openings and closings the writing policy rules out.
BOILERPLATE = (
    "いかがだったでしょうか",
    "いかがでしたでしょうか",
    "ぜひ考えてみてください",
    "今回は",
    "この記事では",
    "近年、",
    "皆さんは",
)

INSTRUCTION_LEAKS = (
    "以下の点に注意して",
    "ご指示のとおり",
    "ご要望に沿って",
)

FENCE = re.compile(r"^\s*```")


def _strip_outer_fence(text: str) -> str:
    """ Remove a code fence wrapping the whole answer. """
    lines = text.strip().split("\n")
    if len(lines) >= 2 and FENCE.match(lines[0]) and FENCE.match(lines[-1]):
        return "\n".join(lines[1:-1]).strip()
    return text.strip()


def _demote_headings(text: str) -> Tuple[str, bool]:
    """ Turn a level one heading into a level two one. """
    result = []
    inside_fence = False
    demoted = False
    for line in text.split("\n"):
        if FENCE.match(line):
            inside_fence = not inside_fence
        elif not inside_fence and re.match(r"^# \S", line):
            line = "#" + line
            demoted = True
        result.append(line)
    return "\n".join(result), demoted


def normalize_body(text: str) -> Tuple[str, List[str]]:
    """ Clean the body and report what deserves a human look. """
    notices: List[str] = []

    body = _strip_outer_fence(text)
    body, demoted = _demote_headings(body)
    if demoted:
        notices.append("The heading level of the body was adjusted.")

    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    if any(phrase in body for phrase in BOILERPLATE):
        notices.append("The body may contain a formulaic opening or closing.")
    if any(phrase in body for phrase in INSTRUCTION_LEAKS):
        notices.append("The body may contain a remark about the work itself.")

    return body, notices
