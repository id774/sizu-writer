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
#  The settings are provider neutral. Using the openai package as a
#  client and talking to OpenAI the company are two different things, so
#  nothing here treats OpenAI as the endpoint a blank setting falls back
#  to: GENERATION_BASE_URL is required and has no default. An endpoint
#  reached by accident is worse than one that refuses to start.
#
#  The module exposes the dataclass Config, load_config() which builds a
#  Config from os.environ, and validate_generation_config() which
#  refuses a configuration that cannot address an endpoint. The split
#  exists so that 'cli.py --version' and the test suite run without a
#  token, while every path that reaches the API passes the second stage.
#  Nothing here performs network access or touches the file system
#  beyond reading .env. The API token never reaches __repr__.
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
#  - GENERATION_BACKEND
#      Wire protocol of the endpoint. Required. 'openai-compatible' is
#      the only value this version accepts; an unknown one is refused
#      rather than read as the default.
#  - GENERATION_API_TOKEN
#      API key or Bearer token of the endpoint. Required. Sakura AI
#      Engine issues it as '<UUID>:<secret>'.
#  - GENERATION_BASE_URL
#      Base URL of the endpoint, including the version path and without
#      the resource name. Required, and https only, so that no request
#      ever leaves for an endpoint nobody named.
#  - GENERATION_MODEL
#      Model used for generation. Required; no default is shipped,
#      because the available models differ per endpoint.
#  - GENERATION_RESPONSE_MODE
#      How a structured answer is asked for: 'json-object' sends
#      response_format, 'prompt-json' asks in the prompt alone.
#      Defaults to prompt-json.
#  - GENERATION_TIMEOUT
#      Seconds allowed for one request. Defaults to 120, which is the
#      time a whole post plus its titles takes on a shared endpoint;
#      the answer is not streamed, so the wait is the generation.
#  - GENERATION_MAX_RETRIES
#      Retries left to the SDK. Defaults to 0, so that one operation
#      spends one request on a plan that counts them.
#  - GENERATION_TEMPERATURE
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
#  v1.1 2026-08-19
#       Refuse non-finite numeric settings before they reach the client
#       or an integer conversion.
#  v1.0 2026-08-05
#       Replace the OPENAI_* settings with provider neutral GENERATION_*
#       ones, require the backend, token, base URL and model instead of
#       falling back to OpenAI, add the response mode, default the
#       retries to zero, refuse the legacy variables by name, and default
#       GENERATION_TIMEOUT to 120 seconds, so that a whole post written
#       by a shared endpoint fits inside one request.
#  v0.1 2026-08-04
#       Initial version.
#
########################################################################

import math
import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Wire protocols this version can speak. A backend is added by writing
# a provider module and naming it here and in sizu_writer/providers;
# see doc/DETAILED_DESIGN_GENERATION_API.md.
GENERATION_BACKENDS = ("openai-compatible",)

# How a structured answer is asked for. There is no 'auto': deciding
# between the two by trying one and retrying with the other turns one
# operation into two requests.
RESPONSE_MODES = ("json-object", "prompt-json")

# The settings these replaced. They are refused rather than translated,
# because a host with a stale OPENAI_API_KEY exported would otherwise
# keep working against an endpoint nobody chose.
LEGACY_VARIABLES = {
    "OPENAI_API_KEY": "GENERATION_API_TOKEN",
    "OPENAI_BASE_URL": "GENERATION_BASE_URL",
    "OPENAI_MODEL": "GENERATION_MODEL",
    "OPENAI_TIMEOUT": "GENERATION_TIMEOUT",
    "OPENAI_MAX_RETRIES": "GENERATION_MAX_RETRIES",
    "OPENAI_TEMPERATURE": "GENERATION_TEMPERATURE",
}

# Resource path the SDK appends itself. A base URL carrying it would
# produce '/chat/completions/chat/completions' at the first request.
RESOURCE_SUFFIX = "/chat/completions"


class ConfigError(ValueError):
    """ Raised when a setting is missing, malformed or no longer used. """


@dataclass
class Config:
    """ Runtime settings of sizu-writer. """

    generation_backend: str = ""
    generation_api_token: str = field(repr=False, default="")
    generation_base_url: str = ""
    generation_model: str = ""
    generation_response_mode: str = "prompt-json"
    generation_timeout: float = 120.0
    generation_max_retries: int = 0
    generation_temperature: Optional[float] = None
    max_output_tokens: int = 6000
    max_input_chars: int = 4000
    max_alt_titles: int = 4
    prompt_dir: str = "prompts"
    log_level: str = "INFO"
    port: int = 8090

    @property
    def endpoint_host(self) -> str:
        """ Return the host of the base URL, for the log. """
        return urlsplit(self.generation_base_url).hostname or ""


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
        value = float(raw)
    except ValueError:
        raise ConfigError("{0} must be a number, got '{1}'".format(name, raw))
    if not math.isfinite(value):
        raise ConfigError("{0} must be a finite number, got '{1}'".format(
            name, raw))
    return value


def _whole(name: str, default: int, minimum: int) -> int:
    """ Read a whole number and refuse one below the given minimum. """
    raw = _text(name, "")
    value = _number(name, float(default))
    if raw and value != int(value):
        raise ConfigError(
            "{0} is '{1}'; expected a whole number.".format(name, raw))
    if value < minimum:
        expected = ("zero or a positive integer" if minimum == 0
                    else "an integer of {0} or more".format(minimum))
        raise ConfigError(
            "{0} is {1}; expected {2}.".format(name, raw, expected))
    return int(value)


def _refuse_legacy_variables() -> None:
    """ Refuse a legacy setting instead of reading it as its successor. """
    for name in sorted(LEGACY_VARIABLES):
        # Presence is what is refused, not the value: an exported but
        # empty OPENAI_BASE_URL still says the host was set up for v1.
        if name in os.environ:
            raise ConfigError(
                "{0} is no longer supported; use {1}.".format(
                    name, LEGACY_VARIABLES[name]))


def load_config() -> Config:
    """ Build a Config from the environment and an optional .env file. """
    if load_dotenv is not None:
        load_dotenv()

    _refuse_legacy_variables()

    # Read through _number so that a bad value is refused with the same
    # message as every other numeric setting, not a bare float() error.
    temperature_raw = _text("GENERATION_TEMPERATURE", "")
    temperature = (_number("GENERATION_TEMPERATURE", 0.0)
                   if temperature_raw else None)

    response_mode = _text("GENERATION_RESPONSE_MODE", "prompt-json")
    if response_mode not in RESPONSE_MODES:
        raise ConfigError(
            "GENERATION_RESPONSE_MODE is '{0}'; expected one of: {1}.".format(
                response_mode, ", ".join(RESPONSE_MODES)))

    timeout = _number("GENERATION_TIMEOUT", 120.0)
    if timeout <= 0:
        raise ConfigError(
            "GENERATION_TIMEOUT is {0}; expected a positive number.".format(
                _text("GENERATION_TIMEOUT", "")))

    port = _whole("PORT", 8090, 1)
    if port > 65535:
        raise ConfigError(
            "PORT is {0}; expected an integer of 1 to 65535.".format(port))

    return Config(
        generation_backend=_text("GENERATION_BACKEND", ""),
        generation_api_token=_text("GENERATION_API_TOKEN", ""),
        generation_base_url=_text("GENERATION_BASE_URL", ""),
        generation_model=_text("GENERATION_MODEL", ""),
        generation_response_mode=response_mode,
        generation_timeout=timeout,
        generation_max_retries=_whole("GENERATION_MAX_RETRIES", 0, 0),
        generation_temperature=temperature,
        max_output_tokens=_whole("MAX_OUTPUT_TOKENS", 6000, 1),
        max_input_chars=_whole("MAX_INPUT_CHARS", 4000, 1),
        max_alt_titles=_whole("MAX_ALT_TITLES", 4, 0),
        prompt_dir=_text("PROMPT_DIR", "prompts"),
        log_level=_text("LOG_LEVEL", "INFO").upper(),
        port=port,
    )


def _validate_base_url(url: str) -> None:
    """ Refuse a base URL that cannot be addressed safely or at all. """
    if not url:
        raise ConfigError("GENERATION_BASE_URL is required.")

    parts = urlsplit(url)
    if parts.scheme == "http":
        raise ConfigError("GENERATION_BASE_URL must use https.")
    if parts.scheme != "https" or not parts.netloc:
        raise ConfigError(
            "GENERATION_BASE_URL must be an absolute https URL, "
            "for example https://api.ai.sakura.ad.jp/v1.")
    if "@" in parts.netloc:
        raise ConfigError(
            "GENERATION_BASE_URL must not carry user information.")
    if parts.query or parts.fragment:
        raise ConfigError(
            "GENERATION_BASE_URL must not carry a query or a fragment.")
    if parts.path.rstrip("/").endswith(RESOURCE_SUFFIX):
        raise ConfigError(
            "GENERATION_BASE_URL must not end with {0}; the SDK appends "
            "the resource path itself.".format(RESOURCE_SUFFIX))


def validate_generation_config(config: Config) -> None:
    """
    Refuse a configuration that cannot address a generation endpoint.

    This runs before any request, at process start and before a CLI
    subcommand, so that a misconfiguration surfaces as a message naming
    the setting rather than as an authentication failure minutes later.
    No message carries a secret: a token is reported as present or
    absent and never quoted.
    """
    if not config.generation_backend:
        raise ConfigError(
            "GENERATION_BACKEND is required; expected: {0}.".format(
                ", ".join(GENERATION_BACKENDS)))
    if config.generation_backend not in GENERATION_BACKENDS:
        raise ConfigError(
            "GENERATION_BACKEND is '{0}'; expected: {1}.".format(
                config.generation_backend, ", ".join(GENERATION_BACKENDS)))

    if not config.generation_api_token:
        raise ConfigError("GENERATION_API_TOKEN is required.")
    if any(character.isspace() for character in config.generation_api_token):
        # The token travels in an Authorization header, which cannot
        # carry a line break. The value itself stays out of the message.
        raise ConfigError(
            "GENERATION_API_TOKEN must not contain whitespace or a line "
            "break.")

    _validate_base_url(config.generation_base_url)

    if not config.generation_model:
        raise ConfigError("GENERATION_MODEL is required.")
