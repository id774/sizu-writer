#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/generator.py: Generation core of sizu-writer
#
#  Description:
#  This module assembles the messages, spends one request through the
#  configured provider, reads the JSON object out of the answer,
#  validates it and returns a Draft. It knows nothing about HTTP, the
#  SDK, the token or the base URL: that all lives in
#  sizu_writer/providers/, so a second wire protocol can be added later
#  without touching what a body and its titles have to look like.
#
#  The answer is requested as JSON so that the body and the titles
#  arrive as separate fields; splitting prose by heuristic is what lets
#  an instruction leak into a post. For the same reason nothing here
#  digs a JSON object out of surrounding prose. Either the whole answer
#  is the object — or, under prompt-json, a single fenced block holding
#  it — or the answer is refused. An endpoint that explains itself first
#  is misconfigured, and reading past the explanation would hide that.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only; the provider brings the client
#
#  Version History:
#  v2.0 2026-08-05
#       Move the API call into sizu_writer/providers/, work from a
#       CompletionResult instead of an SDK response, and read the JSON
#       according to GENERATION_RESPONSE_MODE.
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from config import Config
from sizu_writer import Draft
from sizu_writer.errors import InvalidResponseError
from sizu_writer.formatter import normalize_body
from sizu_writer.prompts import build_body_messages, build_titles_messages
from sizu_writer.providers import CompletionResult, build_provider

logger = logging.getLogger(__name__)


def _complete(messages: List[Dict[str, str]],
              config: Config) -> CompletionResult:
    """ Spend one request through the configured provider. """
    return build_provider(config).complete(messages, config)


def _unwrap_fence(content: str) -> str:
    """
    Return the inside of an answer that is one fenced block, or the
    answer unchanged.

    Only a whole answer wrapped in a single fence is unwrapped. A fence
    with prose around it, or an answer holding more than one fence, is
    left as it is and fails to parse a moment later, which is the
    intended outcome: the model was asked for an object and returned
    something else.
    """
    text = content.strip()
    if not text.startswith("```") or not text.endswith("```"):
        return text

    lines = text.split("\n")
    if len(lines) < 3 or lines[-1].strip() != "```":
        return text
    # Anything but an info string on the opening line means the fence is
    # not the wrapper of the whole answer.
    if "`" in lines[0].strip()[3:]:
        return text

    inner = "\n".join(lines[1:-1])
    if "```" in inner:
        return text
    return inner.strip()


def _payload(content: str, response_mode: str) -> Dict[str, Any]:
    """ Read the JSON object carried by the answer. """
    text = content.strip()
    if response_mode == "prompt-json":
        text = _unwrap_fence(text)

    try:
        payload = json.loads(text)
    except ValueError as error:
        logger.error("The answer is not readable as JSON: %s", error)
        raise InvalidResponseError()

    if not isinstance(payload, dict):
        logger.error("The answer is JSON but not an object")
        raise InvalidResponseError()
    return payload


def _titles(payload: Dict[str, Any], config: Config) -> List[str]:
    """ Validate the titles and keep at most MAX_ALT_TITLES others. """
    primary = payload.get("primary_title")
    if not isinstance(primary, str) or not primary.strip():
        logger.error("The answer has no usable primary_title")
        raise InvalidResponseError()

    others = payload.get("alternative_titles", [])
    if not isinstance(others, list):
        logger.error("alternative_titles is not a list")
        raise InvalidResponseError()

    kept: List[str] = []
    for title in others:
        if not isinstance(title, str):
            logger.error("alternative_titles holds a value that is not a string")
            raise InvalidResponseError()
        title = title.strip()
        if title and title != primary.strip() and title not in kept:
            kept.append(title)

    return [primary.strip()] + kept[:config.max_alt_titles]


def _now() -> str:
    """ Return the current time in ISO 8601. """
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def generate_draft(input_text: str, config: Config) -> Draft:
    """ Generate a post body and its title candidates. """
    result = _complete(build_body_messages(input_text, config.prompt_dir), config)
    payload = _payload(result.content, config.generation_response_mode)

    raw_body = payload.get("body_markdown")
    if not isinstance(raw_body, str) or not raw_body.strip():
        logger.error("The answer has no usable body_markdown")
        raise InvalidResponseError()

    body, notices = normalize_body(raw_body)
    titles = _titles(payload, config)

    return Draft(
        body=body,
        primary_title=titles[0],
        alternative_titles=titles[1:],
        model=result.model or config.generation_model,
        generated_at=_now(),
        notices=notices,
    )


def regenerate_titles(input_text: str, body: str, config: Config) -> Draft:
    """ Generate title candidates for a body that is already settled. """
    messages = build_titles_messages(input_text, body, config.prompt_dir)
    result = _complete(messages, config)
    titles = _titles(_payload(result.content, config.generation_response_mode),
                     config)

    return Draft(
        body=body,
        primary_title=titles[0],
        alternative_titles=titles[1:],
        model=result.model or config.generation_model,
        generated_at=_now(),
        notices=[],
    )
