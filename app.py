#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# app.py: Flask application of sizu-writer
#
#  Description:
#  This module serves the input screen, calls the generation core and
#  renders the result. It keeps no server side state: the input text and
#  the current body travel with the form, so any worker can answer any
#  request and a restart loses nothing.
#
#  Nothing here posts to an external site. The only host contacted is
#  the one named by GENERATION_BASE_URL, and the API token stays in the
#  server process: it reaches neither the templates nor the error pages.
#
#  The generation settings are validated while this module is imported,
#  so a worker that cannot address an endpoint refuses to start instead
#  of accepting a memo and failing on the request. systemd reports the
#  message, which names the setting at fault.
#
#  Routes:
#      /            input screen
#      /generate    generate a body and titles, or titles only
#      /healthz     liveness probe; it calls no API
#
#  Author: id774 (More info: https://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Usage:
#      python app.py
#      gunicorn app:app --bind 127.0.0.1:${PORT:-8090} --timeout 240
#
#  Options:
#  - None. Every setting comes from the environment or .env, through
#    config.py.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Flask 3.x
#
#  Version History:
#  v1.7 2026-09-21
#       Log failures once without raw exception text and show retry controls only
#       for retryable generation errors.
#  v1.6 2026-09-21
#       Preserve body notices across title-only regeneration and retries.
#  v1.5 2026-09-21
#       Add an optional per-request Direction field, validated and preserved
#       across regeneration and retries the same way as the memo.
#  v1.4 2026-09-11
#       Match server input length validation to the browser textarea.
#  v1.3 2026-09-10
#       Preserve title-only state across correctable memo validation errors.
#  v1.2 2026-09-09
#       Reuse one request reference across generation failure diagnostics.
#  v1.1 2026-09-07
#       Keep title-only generation distinct from full generation through retries.
#  v1.0 2026-08-05
#       Validate generation settings at startup so an unusable endpoint never
#       accepts a memo, and answer unknown routes without a traceback.
#  v0.1 2026-08-04
#       Initial release.
#
########################################################################

import logging
import secrets
import traceback

from flask import Flask, g, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import load_config, validate_generation_config
from sizu_writer.diagnostics import reset_reference_id, set_reference_id
from sizu_writer.errors import (DirectionTooLongError, EmptyInputError,
                                InputTooLongError, InternalError,
                                SizuWriterError)
from sizu_writer.generator import generate_draft, regenerate_titles
from sizu_writer.web import STATIC_DIR, TEMPLATE_DIR

config = load_config()

logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Refuse the process rather than the request. A screen offering to
# generate for someone whose server cannot reach an endpoint wastes
# their memo; the operator sees the setting named in the journal.
validate_generation_config(config)

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

# What the screen says about an address the application does not serve.
# The wording is ours rather than the one werkzeug carries, which
# advises checking the spelling of a URL the visitor never typed.
HTTP_MESSAGES = {
    404: "That page does not exist.",
    405: "That address does not accept this kind of request.",
}


def _request_reference_id() -> str:
    """ Return the one diagnostic reference assigned to this request. """
    reference_id = getattr(g, "_sizu_reference_id", None)
    if reference_id is None:
        reference_id = secrets.token_hex(4)
        g._sizu_reference_id = reference_id
        g._sizu_reference_token = set_reference_id(reference_id)
    return reference_id


@app.before_request
def begin_request_diagnostics():
    """ Establish the request reference before application processing. """
    _request_reference_id()


@app.teardown_request
def end_request_diagnostics(_error):
    """ Restore the diagnostic context after this request. """
    token = getattr(g, "_sizu_reference_token", None)
    if token is not None:
        reset_reference_id(token)
        g._sizu_reference_token = None


def _textarea_length(text: str) -> int:
    """ Return the browser textarea length of the submitted text. """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sum(
        2 if ord(character) > 0xffff else 1
        for character in normalized
    )


def _input_text() -> str:
    """ Read the submitted memo and refuse an unusable one. """
    raw = request.form.get("input_text", "")
    text = raw.strip()
    if not text:
        raise EmptyInputError()
    if _textarea_length(raw) > config.max_input_chars:
        raise InputTooLongError(config.max_input_chars)
    return text


def _direction_text() -> str:
    """ Read the optional Direction, blank meaning no additional instruction. """
    raw = request.form.get("direction", "")
    if _textarea_length(raw) > config.max_policy_chars:
        raise DirectionTooLongError(config.max_policy_chars)
    return raw.strip()


@app.route("/")
def index():
    """ Render the input screen. """
    return render_template("index.html", max_input_chars=config.max_input_chars,
                           max_policy_chars=config.max_policy_chars)


@app.route("/generate", methods=["POST"])
def generate():
    """ Generate a whole draft, or only the titles of an existing body. """
    text = _input_text()
    direction = _direction_text()
    body = request.form.get("body", "")
    notices = request.form.getlist("notice")

    mode = request.form.get("mode")
    if mode == "titles":
        draft = regenerate_titles(text, body, config, direction, notices)
    else:
        draft = generate_draft(text, config, direction)

    return render_template("result.html", draft=draft, input_text=text,
                           direction=direction,
                           max_input_chars=config.max_input_chars,
                           max_policy_chars=config.max_policy_chars)


@app.route("/healthz")
def healthz():
    """ Answer that the process is alive without calling the API. """
    return {"status": "ok"}


def _generate_post_in_progress() -> bool:
    """ Return whether the failing request was a POST to /generate. """
    return request.endpoint == "generate" and request.method == "POST"


def _render_sizu_error(error: SizuWriterError, reference_id: str,
                       retryable: bool):
    """ Render the screen for a known error, without logging it. """
    template = "index.html" if error.status_code == 400 else "error.html"
    body = request.form.get("body", "")
    mode = "titles" if request.form.get("mode") == "titles" else "full"

    if error.status_code == 400 and (
            mode != "titles" or not body.strip()):
        mode = "full"

    page = render_template(
        template,
        error=error.user_message,
        reference_id=reference_id,
        input_text=request.form.get("input_text", ""),
        body=body,
        direction=request.form.get("direction", ""),
        mode=mode,
        notices=request.form.getlist("notice"),
        retryable=retryable,
        max_input_chars=config.max_input_chars,
        max_policy_chars=config.max_policy_chars,
    )
    return page, error.status_code


@app.errorhandler(SizuWriterError)
def handle_known_error(error: SizuWriterError):
    """ Show the message meant for the user and log the cause once. """
    reference_id = _request_reference_id()
    # An input the user can correct is not a failure of the server.
    level = logging.INFO if error.status_code == 400 else logging.ERROR
    detail = error.diagnostic or error.user_message
    logger.log(level, "%s (reference %s): %s",
               type(error).__name__, reference_id, detail)

    return _render_sizu_error(error, reference_id, _generate_post_in_progress())


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(error: RequestEntityTooLarge):
    """ Refuse an oversized request without parsing its form again. """
    reference_id = _request_reference_id()
    logger.info("RequestEntityTooLarge (reference %s): %s", reference_id, error)
    page = render_template(
        "error.html",
        error="The request is too large. Reduce its contents and try again.",
        reference_id=reference_id,
        retryable=False,
        max_input_chars=config.max_input_chars,
        max_policy_chars=config.max_policy_chars,
    )
    return page, error.code


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    """
    Answer an address the application does not serve.

    Flask looks an error handler up along the class hierarchy of the
    exception, and every HTTPException is an Exception. Without this
    handler a routing failure reached the one below, which logs a
    traceback and answers 500: a browser asking for /favicon.ico was
    reported as a server that had broken. A page that is not there is
    not a failure of the server, so it keeps its own status and is
    logged as a note.
    """
    reference_id = _request_reference_id()
    level = logging.INFO if error.code < 500 else logging.ERROR
    logger.log(level, "%s (reference %s): %s %s",
               type(error).__name__, reference_id, error.code, request.path)

    page = render_template(
        "error.html",
        error=HTTP_MESSAGES.get(error.code, "The request could not be completed."),
        reference_id=reference_id,
        retryable=False,
        max_input_chars=config.max_input_chars,
        max_policy_chars=config.max_policy_chars,
    )
    return page, error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """ Log a sanitized failure once and show a generic server error. """
    reference_id = _request_reference_id()
    trace = "".join(traceback.format_tb(error.__traceback__)).strip()
    logger.error(
        "Unexpected failure (reference %s): type=%s traceback=%s",
        reference_id,
        type(error).__name__,
        trace or "-",
    )
    return _render_sizu_error(
        InternalError(), reference_id, _generate_post_in_progress())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config.port)
