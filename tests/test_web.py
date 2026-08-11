#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# tests/test_web.py: Tests for app.py
#
#  Description:
#  This test suite drives the Flask application through its test client.
#  It covers the input screen, the liveness probe, the two generation
#  modes, and the refusals the screen has to make on its own: an empty
#  memo, a memo longer than MAX_INPUT_CHARS, and a request larger than
#  the server limit, with the input kept on the page so that nothing
#  typed is lost.
#
#  It also pins the error handling. Each failure is answered with its
#  own status, 404 for an unknown address and 405 for a method the
#  address does not accept included, and no page ever shows a traceback,
#  the requested path or the cause of an upstream failure.
#
#  No request is made. generate_draft and regenerate_titles are replaced
#  by stubs, and app.py is imported with an isolated test configuration so
#  that settings from the host environment or a real .env cannot affect it.
#
#  Author: id774 (More info: http://id774.net)
#  Source Code: https://github.com/id774/sizu-writer
#  License: The GPL version 3, or LGPL version 3 (Dual License).
#  Contact: idnanashi@gmail.com
#
#  Running the tests:
#  Run the whole suite from the repository root:
#      python -m unittest discover -s tests
#  Run this module alone:
#      python -m unittest tests.test_web
#
#  Test Cases:
#    - Show the input screen.
#    - Answer the liveness probe without calling the API.
#    - Keep the input on the page when the memo is too long.
#    - Refuse an empty input.
#    - Refuse a request larger than the server limit with status 413.
#    - Show the body and the titles of a generated draft.
#    - Regenerate the titles of the body it was given, without generating a body.
#    - Hide the cause of a generation failure behind its own status.
#    - Answer an unknown address with 404 rather than 500.
#    - Do not report a missing favicon as a server failure.
#    - Refuse a method the address does not accept with status 405.
#    - Hide the cause and the requested path of a routing failure.
#    - Keep answering an oversized request with 413 rather than the generic status.
#    - Still report an unexpected failure as a server error, without its message.
#    - Do not blame the memo for a timeout.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Flask
#
#  Version History:
#  v1.0 2026-08-05
#       Initial release.
#
########################################################################

import os
import unittest
from unittest import mock

# app.py validates the generation settings while it is imported, so a
# worker that cannot address an endpoint refuses to start. Keep that
# import independent of both the host environment and a local .env.
TEST_ENVIRONMENT = {
    "GENERATION_BACKEND": "openai-compatible",
    "GENERATION_API_TOKEN": "test-token",
    "GENERATION_BASE_URL": "https://api.example.test/v1",
    "GENERATION_MODEL": "test-model",
}
with mock.patch.dict(os.environ, TEST_ENVIRONMENT, clear=True):
    with mock.patch("config.load_dotenv", None):
        import app as web  # noqa: E402  imported with the settings above
from sizu_writer import Draft
from sizu_writer.errors import UpstreamTimeoutError


def draft(body="The body."):
    return Draft(
        body=body,
        primary_title="The leading title",
        alternative_titles=["Another candidate"],
        model="test-model",
        generated_at="2026-08-04T09:00:00+09:00",
        notices=[],
    )


class WebTest(unittest.TestCase):

    def setUp(self):
        web.app.config["TESTING"] = True
        self.client = web.app.test_client()

    def test_shows_the_input_screen(self):
        answer = self.client.get("/")

        self.assertEqual(200, answer.status_code)
        self.assertIn("input_text", answer.get_data(as_text=True))

    def test_answers_the_liveness_probe_without_calling_the_api(self):
        with mock.patch.object(web, "generate_draft") as generate:
            answer = self.client.get("/healthz")

        self.assertEqual(200, answer.status_code)
        generate.assert_not_called()

    def test_keeps_the_input_when_it_is_too_long(self):
        text = "a" * (web.config.max_input_chars + 1)

        answer = self.client.post("/generate", data={"input_text": text, "mode": "full"})

        self.assertEqual(400, answer.status_code)
        self.assertIn("The memo is too long", answer.get_data(as_text=True))
        self.assertIn(text, answer.get_data(as_text=True))

    def test_refuses_an_empty_input(self):
        answer = self.client.post("/generate", data={"input_text": "  ", "mode": "full"})

        self.assertEqual(400, answer.status_code)
        self.assertIn("Enter a memo first", answer.get_data(as_text=True))

    def test_refuses_a_request_larger_than_the_server_limit(self):
        text = "a" * (web.app.config["MAX_CONTENT_LENGTH"] + 1)

        answer = self.client.post("/generate", data={"input_text": text, "mode": "full"})

        self.assertEqual(413, answer.status_code)
        self.assertIn("The request is too large", answer.get_data(as_text=True))

    def test_shows_the_body_and_the_titles_of_a_draft(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        generate.assert_called_once()
        page = answer.get_data(as_text=True)
        self.assertIn("The body.", page)
        self.assertIn("The leading title", page)
        self.assertIn("Another candidate", page)

    def test_regenerates_the_titles_of_the_body_it_was_given(self):
        with mock.patch.object(web, "regenerate_titles", return_value=draft("The settled body")) as titles:
            with mock.patch.object(web, "generate_draft") as generate:
                answer = self.client.post("/generate", data={
                    "input_text": "a memo", "body": "The settled body", "mode": "titles"})

        generate.assert_not_called()
        titles.assert_called_once()
        self.assertIn("The settled body", answer.get_data(as_text=True))

    def test_hides_the_cause_of_a_generation_failure(self):
        with mock.patch.object(web, "generate_draft", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(504, answer.status_code)
        self.assertIn("Generation took too long", page)
        self.assertNotIn("Traceback", page)

    def test_answers_an_unknown_address_with_not_found(self):
        # Flask looks a handler up along the class hierarchy, and every
        # HTTPException is an Exception. Without a handler of its own a
        # missing page reached the catch-all one and was answered 500.
        answer = self.client.get("/nothing-here")

        self.assertEqual(404, answer.status_code)
        self.assertIn("That page does not exist", answer.get_data(as_text=True))

    def test_does_not_report_a_missing_favicon_as_a_server_failure(self):
        # A browser asks for it on its own. It is not a request anyone
        # made, and it must not be logged as the server having broken.
        answer = self.client.get("/favicon.ico")

        self.assertEqual(404, answer.status_code)

    def test_refuses_a_method_the_address_does_not_accept(self):
        answer = self.client.post("/healthz")

        self.assertEqual(405, answer.status_code)

    def test_hides_the_cause_of_a_routing_failure(self):
        page = self.client.get("/nothing-here").get_data(as_text=True)

        self.assertNotIn("Traceback", page)
        self.assertNotIn("nothing-here", page)

    def test_still_refuses_an_oversized_request_with_its_own_status(self):
        # The handler for 413 is more specific than the one for every
        # HTTPException, so adding the latter must not shadow it.
        text = "a" * (web.app.config["MAX_CONTENT_LENGTH"] + 1)

        answer = self.client.post("/generate", data={"input_text": text, "mode": "full"})

        self.assertEqual(413, answer.status_code)
        self.assertIn("The request is too large", answer.get_data(as_text=True))

    def test_still_reports_an_unexpected_failure_as_a_server_error(self):
        with mock.patch.object(web, "generate_draft", side_effect=RuntimeError("boom")):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(500, answer.status_code)
        self.assertIn("The server failed to handle the request", page)
        self.assertNotIn("boom", page)

    def test_does_not_blame_the_memo_for_a_timeout(self):
        # The wait is the answer being written, not the memo being read.
        # A one line memo asks for the same post as a long one, so advice
        # to shorten it sends the person editing while nothing changes.
        with mock.patch.object(web, "generate_draft", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        self.assertNotIn("Shorten the memo", answer.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
