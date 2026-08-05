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
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Usage:
#      python app.py
#      gunicorn app:app --bind 127.0.0.1:${PORT} --timeout 240
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
#  v1.2 2026-08-05
#       Answer an unknown address with its own status. A missing page
#       was reported as a server failure, and a browser asking for
#       /favicon.ico was enough to log a traceback.
#  v1.1 2026-08-05
#       Validate the generation settings at startup, so that a worker
#       without a usable endpoint never accepts a memo.
#  v1.0 2026-08-04
#       Initial release.
#
########################################################################

import logging
import secrets

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import load_config, validate_generation_config
from sizu_writer.errors import (EmptyInputError, InputTooLongError,
                                InternalError, SizuWriterError)
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


def _input_text() -> str:
    """ Read the submitted memo and refuse an unusable one. """
    text = request.form.get("input_text", "").strip()
    if not text:
        raise EmptyInputError()
    if len(text) > config.max_input_chars:
        raise InputTooLongError(config.max_input_chars)
    return text


@app.route("/")
def index():
    """ Render the input screen. """
    return render_template("index.html", max_input_chars=config.max_input_chars)


@app.route("/generate", methods=["POST"])
def generate():
    """ Generate a whole draft, or only the titles of an existing body. """
    text = _input_text()
    body = request.form.get("body", "")

    if request.form.get("mode") == "titles" and body.strip():
        draft = regenerate_titles(text, body, config)
    else:
        draft = generate_draft(text, config)

    return render_template("result.html", draft=draft, input_text=text,
                           max_input_chars=config.max_input_chars)


@app.route("/healthz")
def healthz():
    """ Answer that the process is alive without calling the API. """
    return {"status": "ok"}


@app.errorhandler(SizuWriterError)
def handle_known_error(error: SizuWriterError):
    """ Show the message meant for the user and log the cause. """
    reference_id = secrets.token_hex(4)
    # An input the user can correct is not a failure of the server.
    level = logging.INFO if error.status_code == 400 else logging.ERROR
    logger.log(level, "%s (reference %s): %s", type(error).__name__, reference_id, error)

    template = "index.html" if error.status_code == 400 else "error.html"
    page = render_template(
        template,
        error=error.user_message,
        reference_id=reference_id,
        input_text=request.form.get("input_text", ""),
        body=request.form.get("body", ""),
        max_input_chars=config.max_input_chars,
    )
    return page, error.status_code


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(error: RequestEntityTooLarge):
    """ Refuse an oversized request without parsing its form again. """
    reference_id = secrets.token_hex(4)
    logger.info("RequestEntityTooLarge (reference %s): %s", reference_id, error)
    page = render_template(
        "error.html",
        error="The request is too large. Reduce its contents and try again.",
        reference_id=reference_id,
        max_input_chars=config.max_input_chars,
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
    reference_id = secrets.token_hex(4)
    level = logging.INFO if error.code < 500 else logging.ERROR
    logger.log(level, "%s (reference %s): %s %s",
               type(error).__name__, reference_id, error.code, request.path)

    page = render_template(
        "error.html",
        error=HTTP_MESSAGES.get(error.code, "The request could not be completed."),
        reference_id=reference_id,
        max_input_chars=config.max_input_chars,
    )
    return page, error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """ Report an unexpected failure without exposing its detail. """
    logger.exception("Unexpected failure: %s", error)
    return handle_known_error(InternalError(str(error)))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config.port)
