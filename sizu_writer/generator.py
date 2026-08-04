#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/generator.py: Generation core of sizu-writer
#
#  Description:
#  This module calls an OpenAI compatible endpoint, validates the answer
#  and returns a Draft. The answer is requested as JSON so that the body
#  and the titles arrive as separate fields; splitting prose by heuristic
#  is what lets an instruction leak into a post. Retries are left to the
#  SDK, and the endpoint is the only host this system ever talks to.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - openai
#
#  Version History:
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
from sizu_writer.errors import (InternalError, InvalidResponseError,
                                UpstreamConnectionError, UpstreamStatusError,
                                UpstreamTimeoutError)
from sizu_writer.formatter import normalize_body
from sizu_writer.prompts import build_body_messages, build_titles_messages

logger = logging.getLogger(__name__)


def _client(config: Config):
    """ Build the OpenAI client described by the configuration. """
    try:
        from openai import OpenAI
    except ImportError as error:
        logger.error("The openai package is not installed: %s", error)
        raise InternalError("openai package missing")

    if not config.openai_api_key:
        logger.error("OPENAI_API_KEY is not set")
        raise InternalError("api key missing")
    if not config.openai_model:
        logger.error("OPENAI_MODEL is not set")
        raise InternalError("model missing")

    arguments: Dict[str, Any] = {
        "api_key": config.openai_api_key,
        "timeout": config.openai_timeout,
        "max_retries": config.openai_max_retries,
    }
    if config.openai_base_url:
        arguments["base_url"] = config.openai_base_url
    return OpenAI(**arguments)


def _complete(messages: List[Dict[str, str]], config: Config) -> Any:
    """ Send one chat completion request and map its failures. """
    import openai

    arguments: Dict[str, Any] = {
        "model": config.openai_model,
        "messages": messages,
        "max_tokens": config.max_output_tokens,
        "response_format": {"type": "json_object"},
    }
    if config.openai_temperature is not None:
        arguments["temperature"] = config.openai_temperature

    try:
        return _client(config).chat.completions.create(**arguments)
    except openai.APITimeoutError as error:
        logger.error("The request timed out after %s seconds: %s", config.openai_timeout, error)
        raise UpstreamTimeoutError()
    except openai.APIConnectionError as error:
        logger.error("Cannot reach the endpoint: %s", error)
        raise UpstreamConnectionError()
    except openai.APIStatusError as error:
        logger.error("The endpoint answered with status %s: %s", error.status_code, error)
        raise UpstreamStatusError()


def _payload(response: Any) -> Dict[str, Any]:
    """ Read the JSON object carried by the answer. """
    choices = getattr(response, "choices", None)
    if not choices:
        logger.error("The answer carries no choice")
        raise InvalidResponseError()

    choice = choices[0]
    if getattr(choice, "finish_reason", None) == "length":
        logger.error("The output was cut off; raise MAX_OUTPUT_TOKENS or shorten the input")
        raise InvalidResponseError()

    try:
        payload = json.loads(choice.message.content)
    except (AttributeError, TypeError, ValueError) as error:
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
    response = _complete(build_body_messages(input_text, config.prompt_dir), config)
    payload = _payload(response)

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
        model=getattr(response, "model", config.openai_model),
        generated_at=_now(),
        notices=notices,
    )


def regenerate_titles(input_text: str, body: str, config: Config) -> Draft:
    """ Generate title candidates for a body that is already settled. """
    response = _complete(build_titles_messages(input_text, body, config.prompt_dir), config)
    titles = _titles(_payload(response), config)

    return Draft(
        body=body,
        primary_title=titles[0],
        alternative_titles=titles[1:],
        model=getattr(response, "model", config.openai_model),
        generated_at=_now(),
        notices=[],
    )
