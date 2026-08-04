#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# config.py: Central configuration for sizu-writer
#
#  Description:
#  This module collects every runtime setting of sizu-writer in a single
#  place. All settings are read from environment variables (optionally
#  loaded from a local .env file) so that the same code base runs
#  unchanged on a workstation and on a server behind Apache.
#
#  The module exposes the dataclass Config and the helper load_config()
#  which builds a Config from os.environ. Nothing here performs network
#  access or touches the file system beyond reading .env, so it is safe
#  to import from anywhere. The API key never reaches __repr__.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - python-dotenv
#
#  Environment Variables:
#  - OPENAI_API_KEY
#      API key of the OpenAI compatible endpoint. Required at generation
#      time; a missing key is reported to the log, never to the screen.
#  - OPENAI_BASE_URL
#      Base URL of an OpenAI compatible endpoint. Empty means OpenAI.
#  - OPENAI_MODEL
#      Model used for generation. No default: a sensible one differs per
#      endpoint.
#  - OPENAI_TIMEOUT
#      Seconds allowed for one request. Defaults to 60.
#  - OPENAI_MAX_RETRIES
#      Retries left to the SDK. Defaults to 2; 0 spends one request.
#  - OPENAI_TEMPERATURE
#      Sent only when set, so that a model refusing the parameter works.
#  - MAX_OUTPUT_TOKENS
#      Upper bound of one response. Defaults to 6000.
#  - MAX_INPUT_CHARS
#      Upper bound of the input field. Defaults to 4000.
#  - MAX_ALT_TITLES
#      Number of alternative titles kept. Defaults to 4.
#  - PROMPT_DIR
#      Directory holding the prompt files. Defaults to 'prompts'.
#  - LOG_LEVEL
#      Level of the application log. Defaults to INFO.
#  - PORT
#      Port of the development server and of gunicorn. Defaults to 8090.
#
#  Version History:
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


@dataclass
class Config:
    """ Runtime settings of sizu-writer. """

    openai_api_key: str = field(repr=False, default="")
    openai_base_url: str = ""
    openai_model: str = ""
    openai_timeout: float = 60.0
    openai_max_retries: int = 2
    openai_temperature: Optional[float] = None
    max_output_tokens: int = 6000
    max_input_chars: int = 4000
    max_alt_titles: int = 4
    prompt_dir: str = "prompts"
    log_level: str = "INFO"
    port: int = 8090


def _text(name: str, default: str) -> str:
    """ Read a setting and fall back to the default when it is blank. """
    value = os.environ.get(name, "")
    value = value.strip()
    return value if value else default


def _number(name: str, default: float) -> float:
    """ Read a numeric setting, keeping the default on a bad value. """
    raw = _text(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError("{0} must be a number, got '{1}'".format(name, raw))


def load_config() -> Config:
    """ Build a Config from the environment and an optional .env file. """
    if load_dotenv is not None:
        load_dotenv()

    # Read through _number so that a bad value is refused with the same
    # message as every other numeric setting, not a bare float() error.
    temperature_raw = _text("OPENAI_TEMPERATURE", "")
    temperature = _number("OPENAI_TEMPERATURE", 0.0) if temperature_raw else None

    return Config(
        openai_api_key=_text("OPENAI_API_KEY", ""),
        openai_base_url=_text("OPENAI_BASE_URL", ""),
        openai_model=_text("OPENAI_MODEL", ""),
        openai_timeout=_number("OPENAI_TIMEOUT", 60.0),
        openai_max_retries=int(_number("OPENAI_MAX_RETRIES", 2)),
        openai_temperature=temperature,
        max_output_tokens=int(_number("MAX_OUTPUT_TOKENS", 6000)),
        max_input_chars=int(_number("MAX_INPUT_CHARS", 4000)),
        max_alt_titles=int(_number("MAX_ALT_TITLES", 4)),
        prompt_dir=_text("PROMPT_DIR", "prompts"),
        log_level=_text("LOG_LEVEL", "INFO").upper(),
        port=int(_number("PORT", 8090)),
    )
