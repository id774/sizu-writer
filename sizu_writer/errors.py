#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/errors.py: Error hierarchy of sizu-writer
#
#  Description:
#  Every failure the user is allowed to see is represented here as an
#  exception carrying a message and an HTTP status code. The screen
#  shows user_message only: the exception text, the traceback, the
#  endpoint URL and the model name stay in the server log, so that an
#  error page cannot leak internal information.
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
#  v2.0 2026-08-05
#       Name GENERATION_TIMEOUT as the limit a timeout reports.
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################


class SizuWriterError(Exception):
    """ Base of every error the user is allowed to see. """

    user_message = "The request could not be completed."
    status_code = 500


class EmptyInputError(SizuWriterError):
    """ Raised when the input is empty or blank. """

    user_message = "Enter a memo first."
    status_code = 400


class InputTooLongError(SizuWriterError):
    """ Raised when the input exceeds MAX_INPUT_CHARS. """

    status_code = 400

    def __init__(self, limit: int) -> None:
        self.user_message = "The memo is too long. Keep it within {0} characters.".format(limit)
        super().__init__(self.user_message)


class UpstreamConnectionError(SizuWriterError):
    """ Raised when the endpoint cannot be reached. """

    user_message = "The generation service could not be reached. Try again in a while."
    status_code = 502


class UpstreamTimeoutError(SizuWriterError):
    """ Raised when one request exceeds GENERATION_TIMEOUT. """

    user_message = "Generation took too long and was stopped. Shorten the memo, or try again in a while."
    status_code = 504


class UpstreamStatusError(SizuWriterError):
    """ Raised on a 4xx or 5xx answer, including auth and rate limits. """

    user_message = "The generation service answered with an error. Try again in a while."
    status_code = 502


class InvalidResponseError(SizuWriterError):
    """ Raised when the answer cannot be read as the expected result. """

    user_message = "The result could not be read. Generate it once more."
    status_code = 502


class InternalError(SizuWriterError):
    """ Raised for every unexpected failure inside the server. """

    user_message = "The server failed to handle the request."
    status_code = 500
