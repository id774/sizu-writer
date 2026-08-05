#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/providers/__init__.py: Choice of the generation transport
#
#  Description:
#  This package holds everything that knows how a generation endpoint is
#  spoken to: the SDK, the authentication, the base URL, the shape of a
#  request and the exceptions the client raises. Nothing above it does.
#  generator.py hands over a message list and receives a
#  CompletionResult, so adding a second wire protocol later leaves the
#  validation of a body and its titles untouched.
#
#  The backend is chosen by name, from GENERATION_BACKEND, and only from
#  there. A value this version does not know is refused before a request
#  is made rather than read as the default one, because a system that
#  guesses which endpoint was meant will eventually guess wrong and send
#  a memo somewhere nobody chose.
#
#  Adding a backend is three steps: write a module in this package
#  exposing a class with complete(), register it in BACKENDS below, and
#  name the value in GENERATION_BACKENDS of config.py. Nothing else in
#  the repository has to change; see
#  doc/DETAILED_DESIGN_GENERATION_API.md.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only; a provider module brings its own client
#
#  Version History:
#  v1.0 2026-08-05
#       Initial version, with the OpenAI compatible backend. Carry the
#       elapsed seconds of one request in CompletionResult and record
#       them, next to the limit, on the response line.
#
########################################################################

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol

from config import Config
from sizu_writer.errors import InternalError

logger = logging.getLogger(__name__)


@dataclass
class CompletionResult:
    """
    One answer, normalized away from the client that produced it.

    Only content is required. A compatible endpoint may report no usage
    and no request id, and a draft is still usable without them, so a
    missing count is carried as None rather than treated as a failure.

    elapsed_seconds is measured on this side rather than read from the
    answer, so it is present whatever the endpoint reports.
    """

    content: str
    model: str = ""
    finish_reason: str = ""
    request_id: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    elapsed_seconds: Optional[float] = None


class GenerationProvider(Protocol):
    """
    The interface generator.py depends on.

    A provider turns a message list into a CompletionResult, spending
    exactly one request, and raises the Upstream* errors of
    sizu_writer.errors for a failure the user may be told about. It
    never inspects the JSON inside the answer: what a body and its
    titles have to look like is not a property of the wire protocol.
    """

    def complete(self, messages: List[Dict[str, str]],
                 config: Config) -> CompletionResult:
        ...


def _openai_compatible() -> Callable[[], GenerationProvider]:
    """ Import the OpenAI compatible provider on demand. """
    from sizu_writer.providers.openai_compatible import \
        OpenAICompatibleProvider
    return OpenAICompatibleProvider


# Backends this version can speak, by the name GENERATION_BACKEND takes.
# The values are loaders rather than classes, so that importing this
# package does not import an SDK a deployment may not need.
BACKENDS: Dict[str, Callable[[], Callable[[], GenerationProvider]]] = {
    "openai-compatible": _openai_compatible,
}


def build_provider(config: Config) -> GenerationProvider:
    """
    Return the provider named by GENERATION_BACKEND.

    Raises:
        InternalError: The backend is unknown. config.validate_
            generation_config() refuses that earlier and with a better
            message; reaching here means the two lists disagree, which
            is a fault of this repository and not of the operator.
    """
    loader = BACKENDS.get(config.generation_backend)
    if loader is None:
        logger.error("GENERATION_BACKEND '%s' has no provider; known: %s",
                     config.generation_backend, ", ".join(sorted(BACKENDS)))
        raise InternalError("unknown generation backend")
    return loader()()


def log_response(config: Config, result: CompletionResult) -> None:
    """
    Record the shape of one answer, and none of its content.

    The memo, the prompt, the generated body and the token stay out of
    the log at every level. What is left is what an operator needs to
    match a run against the usage counted by the provider.

    The elapsed seconds are part of that shape. A run that succeeded in
    almost the whole of GENERATION_TIMEOUT is the same event as the
    timeout that follows it, seen one moment earlier, and only a log
    that records the successful ones can show that the margin was
    already gone.
    """
    logger.info(
        "generation response: backend=%s endpoint_host=%s request_id=%s "
        "model=%s finish_reason=%s prompt_tokens=%s completion_tokens=%s "
        "total_tokens=%s elapsed=%s timeout=%s",
        config.generation_backend,
        config.endpoint_host,
        result.request_id or "-",
        result.model or "-",
        result.finish_reason or "-",
        result.prompt_tokens,
        result.completion_tokens,
        result.total_tokens,
        result.elapsed_seconds if result.elapsed_seconds is not None else "-",
        config.generation_timeout,
    )
