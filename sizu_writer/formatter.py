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
#  v1.3 2026-09-12
#       Demote valid level-one ATX headings with Markdown indentation and separators.
#  v1.2 2026-09-09
#       Preserve headings and blank lines inside backtick and tilde code fences.
#  v1.1 2026-08-11
#       Preserve separate code blocks at the boundaries of a body.
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

import re
from typing import List, Optional, Tuple

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

FENCE = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})(?P<rest>.*)$")

ATX_H1 = re.compile(r"^(?P<indent> {0,3})#(?=$|[ \t])")


def _fence(line: str) -> Optional[Tuple[str, int, str]]:
    """ Return the marker, its length and the text after a fence. """
    match = FENCE.match(line)
    if match is None:
        return None
    marker = match.group("marker")
    return marker[0], len(marker), match.group("rest")


def _closes_fence(line: str, opening: Tuple[str, int]) -> bool:
    """ Return whether a line closes the given fenced code block. """
    fence = _fence(line)
    if fence is None:
        return False
    marker, length, rest = fence
    return (
        marker == opening[0]
        and length >= opening[1]
        and not rest.strip()
    )


def _strip_outer_fence(text: str) -> str:
    """ Remove a code fence wrapping the whole answer. """
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return text.strip()

    opening_fence = _fence(lines[0])
    if opening_fence is None:
        return text.strip()

    opening = (opening_fence[0], opening_fence[1])
    if not _closes_fence(lines[-1], opening):
        return text.strip()

    inner_has_fence = any(_fence(line) is not None for line in lines[1:-1])
    if inner_has_fence:
        return text.strip()

    return "\n".join(lines[1:-1]).strip()


def _demote_headings(text: str) -> Tuple[str, bool]:
    """ Turn a level one heading into a level two one. """
    result = []
    opening: Optional[Tuple[str, int]] = None
    demoted = False
    for line in text.split("\n"):
        if opening is not None:
            if _closes_fence(line, opening):
                opening = None
            result.append(line)
            continue

        fence = _fence(line)
        if fence is not None:
            opening = (fence[0], fence[1])
        else:
            heading = ATX_H1.match(line)
            if heading is not None:
                indent = heading.group("indent")
                line = "{0}#{1}".format(indent, line[len(indent):])
                demoted = True
        result.append(line)
    return "\n".join(result), demoted


def _collapse_blank_lines(text: str) -> str:
    """ Collapse runs of blank lines outside fenced code blocks. """
    opening: Optional[Tuple[str, int]] = None
    previous_empty = False
    result: List[str] = []

    for line in text.split("\n"):
        if opening is not None:
            result.append(line)
            if _closes_fence(line, opening):
                opening = None
            continue

        fence = _fence(line)
        if fence is not None:
            opening = (fence[0], fence[1])
            result.append(line)
            previous_empty = False
            continue

        if line == "":
            if not previous_empty:
                result.append(line)
            previous_empty = True
        else:
            result.append(line)
            previous_empty = False

    return "\n".join(result)


def normalize_body(text: str) -> Tuple[str, List[str]]:
    """ Clean the body and report what deserves a human look. """
    notices: List[str] = []

    body = _strip_outer_fence(text)
    body, demoted = _demote_headings(body)
    if demoted:
        notices.append("The heading level of the body was adjusted.")

    body = _collapse_blank_lines(body).strip()

    if any(phrase in body for phrase in BOILERPLATE):
        notices.append("The body may contain a formulaic opening or closing.")
    if any(phrase in body for phrase in INSTRUCTION_LEAKS):
        notices.append("The body may contain a remark about the work itself.")

    return body, notices
