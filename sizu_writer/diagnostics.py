#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/diagnostics.py: Request-scoped diagnostic reference
#
#  Description:
#  This module holds the one diagnostic reference id of the current
#  request, in a ContextVar rather than a Flask object. app.py sets it
#  before generation runs, and the provider layer reads it when a
#  generation failure is logged, so that a provider log line and the
#  error page shown for the same request carry the same id without
#  either layer importing the other.
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
#  v0.1 2026-09-09
#       Initial release.
#
########################################################################

from contextvars import ContextVar, Token
from typing import Optional

_reference_id: ContextVar[Optional[str]] = ContextVar(
    "sizu_writer_reference_id",
    default=None,
)


def set_reference_id(reference_id: str) -> Token:
    """ Set the diagnostic reference for the current execution context. """
    return _reference_id.set(reference_id)


def get_reference_id() -> Optional[str]:
    """ Return the diagnostic reference of the current execution context. """
    return _reference_id.get()


def reset_reference_id(token: Token) -> None:
    """ Restore the diagnostic reference that preceded the given token. """
    _reference_id.reset(token)
