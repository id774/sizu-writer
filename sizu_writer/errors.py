#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# sizu_writer/errors.py: Error hierarchy of sizu-writer
#
#  Description:
#  Every failure the user is allowed to see is represented here as an
#  exception carrying a Japanese message and an HTTP status code. The
#  screen shows user_message only: the exception text, the traceback,
#  the endpoint URL and the model name stay in the server log, so that
#  an error page cannot leak internal information.
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


class SizuWriterError(Exception):
    """ Base of every error the user is allowed to see. """

    user_message = "処理に失敗しました。"
    status_code = 500


class EmptyInputError(SizuWriterError):
    """ Raised when the input is empty or blank. """

    user_message = "短文を入力してください。"
    status_code = 400


class InputTooLongError(SizuWriterError):
    """ Raised when the input exceeds MAX_INPUT_CHARS. """

    status_code = 400

    def __init__(self, limit: int) -> None:
        self.user_message = "入力が長すぎます。{0} 字以内にしてください。".format(limit)
        super().__init__(self.user_message)


class UpstreamConnectionError(SizuWriterError):
    """ Raised when the endpoint cannot be reached. """

    user_message = "文章生成サービスへ接続できませんでした。時間をおいて再度お試しください。"
    status_code = 502


class UpstreamTimeoutError(SizuWriterError):
    """ Raised when one request exceeds OPENAI_TIMEOUT. """

    user_message = "生成に時間がかかりすぎたため中断しました。入力を短くするか、時間をおいてお試しください。"
    status_code = 504


class UpstreamStatusError(SizuWriterError):
    """ Raised on a 4xx or 5xx answer, including auth and rate limits. """

    user_message = "文章生成サービスがエラーを返しました。時間をおいて再度お試しください。"
    status_code = 502


class InvalidResponseError(SizuWriterError):
    """ Raised when the answer cannot be read as the expected result. """

    user_message = "生成結果を読み取れませんでした。もう一度生成してください。"
    status_code = 502


class InternalError(SizuWriterError):
    """ Raised for every unexpected failure inside the server. """

    user_message = "サーバー内部で処理に失敗しました。"
    status_code = 500
