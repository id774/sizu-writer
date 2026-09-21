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
#  the server limit. Correctable memo validation errors keep the input
#  on the page; an oversized request is handled without reparsing its
#  form.
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
#  This suite also checks the contract between the rendered HTML and the
#  served JavaScript asset through the Flask test client: the markup a
#  progressive helper hooks onto, and the source of the helper itself. It
#  does not run a JavaScript engine.
#
#  Author: id774 (More info: https://id774.net)
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
#    - Count supplementary Unicode characters like the browser textarea.
#    - Count textarea CRLF as one normalized newline.
#    - Count surrounding whitespace toward MAX_INPUT_CHARS.
#    - Refuse an empty input.
#    - Refuse a request larger than the server limit with status 413.
#    - Show the body and the titles of a generated draft.
#    - Regenerate the titles of the body it was given, without generating a body.
#    - Refuse title regeneration without a body instead of generating a full draft.
#    - Keep title-only mode and its body on a generation failure.
#    - Keep full generation as the retry mode after a full-generation failure.
#    - Hide the cause of a generation failure behind its own status.
#    - Answer an unknown address with 404 rather than 500.
#    - Do not report a missing favicon as a server failure.
#    - Refuse a method the address does not accept with status 405.
#    - Hide the cause and the requested path of a routing failure.
#    - Keep answering an oversized request with 413 rather than the generic status.
#    - Still report an unexpected failure as a server error, without its message.
#    - Do not blame the memo for a timeout.
#    - Keep one request reference through a generation failure and clear it afterwards.
#    - Keep title-only mode and its body when memo validation fails.
#    - Return to full generation when title-only regeneration has no body.
#    - Render the input character-count hook and configured limit.
#    - Limit the result memo and mark the post body for automatic growth.
#    - Serve progressive submit, character-count and auto-grow helpers.
#    - Preserve the clicked submit value before disabling generation buttons.
#    - Render the optional direction field with its own character-count hook.
#    - Generate normally when the direction is blank.
#    - Pass a nonblank direction to full generation.
#    - Pass a nonblank direction to title-only regeneration.
#    - Refuse an overlong direction with 400 before calling generation.
#    - Preserve the direction across a correctable memo validation error.
#    - Preserve the direction across full regeneration from the result screen.
#    - Preserve the direction across title-only regeneration.
#    - Preserve the direction on a title-only retry after a generation failure.
#    - Preserve the direction on a full-generation retry after a failure.
#    - Keep the direction out of the application log.
#    - Start a new input screen with a blank direction.
#    - Clear the memo and Direction together and reset both character counts.
#    - Preserve existing body notices as hidden fields on the result screen.
#    - Pass existing notices to title-only regeneration.
#    - Preserve notices across a title-only retry and a correctable title-only
#      validation error.
#    - Ignore submitted notices during full regeneration.
#    - Show no generation retry controls on the 404, 405 and 413 error pages.
#    - Keep a retryable generation form on an unexpected /generate failure.
#    - Log an unexpected failure once, without its raw exception message.
#    - Accept a same-origin generation POST, including an https Origin behind
#      TLS termination.
#    - Refuse a missing, malformed or foreign Origin before generation, with
#      no form reflection and no raw Origin in the log.
#    - Allow the previous behavior when REQUIRE_SAME_ORIGIN is disabled.
#    - Leave non-generation routes and request ordering unaffected by the
#      same-origin guard.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Flask
#
#  Version History:
#  v1.5 2026-09-21
#       Cover Direction/notices/error retries and default-on same-origin
#       protection for Web generation POSTs.
#  v1.4 2026-09-11
#       Cover browser-equivalent MAX_INPUT_CHARS validation on the server.
#  v1.3 2026-09-10
#       Cover title-only state across correctable memo validation errors, and
#       the Web progressive enhancement markup and script contract.
#  v1.2 2026-09-09
#       Cover one request reference across generation failure handling.
#  v1.1 2026-09-07
#       Cover title-only body refusal and preservation of the retry operation.
#  v1.0 2026-08-05
#       Initial release.
#
########################################################################

import logging
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
from sizu_writer.diagnostics import get_reference_id
from sizu_writer.errors import EmptyBodyError, UpstreamTimeoutError


def draft(body="The body.", notices=None):
    return Draft(
        body=body,
        primary_title="The leading title",
        alternative_titles=["Another candidate"],
        model="test-model",
        generated_at="2026-08-04T09:00:00+09:00",
        notices=list(notices) if notices is not None else [],
    )


class WebTest(unittest.TestCase):

    def setUp(self):
        web.app.config["TESTING"] = True
        self.client = web.app.test_client()
        self.client.environ_base["HTTP_ORIGIN"] = "http://localhost"

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

    def test_counts_supplementary_unicode_like_the_browser_limit(self):
        with mock.patch.object(web.config, "max_input_chars", 1):
            with mock.patch.object(
                    web, "generate_draft", return_value=draft()) as generate:
                answer = self.client.post("/generate", data={
                    "input_text": "😀",
                    "mode": "full",
                })

        self.assertEqual(400, answer.status_code)
        self.assertIn("The memo is too long", answer.get_data(as_text=True))
        generate.assert_not_called()

    def test_counts_crlf_as_one_textarea_newline(self):
        with mock.patch.object(web.config, "max_input_chars", 3):
            with mock.patch.object(
                    web, "generate_draft", return_value=draft()) as generate:
                answer = self.client.post("/generate", data={
                    "input_text": "a\r\nb",
                    "mode": "full",
                })

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once_with("a\r\nb", web.config, "")

    def test_counts_surrounding_whitespace_toward_the_input_limit(self):
        with mock.patch.object(web.config, "max_input_chars", 1):
            with mock.patch.object(
                    web, "generate_draft", return_value=draft()) as generate:
                answer = self.client.post("/generate", data={
                    "input_text": " a ",
                    "mode": "full",
                })

        self.assertEqual(400, answer.status_code)
        self.assertIn("The memo is too long", answer.get_data(as_text=True))
        generate.assert_not_called()

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

        titles.assert_called_once_with("a memo", "The settled body", web.config, "", [])
        generate.assert_not_called()
        self.assertIn("The settled body", answer.get_data(as_text=True))

    def test_refuses_title_regeneration_without_a_body(self):
        for body in ("", "   \n"):
            with self.subTest(body=repr(body)):
                with mock.patch.object(
                        web, "regenerate_titles",
                        side_effect=EmptyBodyError()) as titles:
                    with mock.patch.object(web, "generate_draft") as generate:
                        answer = self.client.post("/generate", data={
                            "input_text": "a memo",
                            "body": body,
                            "mode": "titles",
                        })

                page = answer.get_data(as_text=True)
                self.assertEqual(400, answer.status_code)
                self.assertIn(
                    "There is no post body to regenerate titles for.", page)
                self.assertIn('name="mode" value="full"', page)
                self.assertIn(">Generate<", page)
                self.assertNotIn("Regenerate the titles only", page)
                self.assertNotIn('name="body"', page)
                titles.assert_called_once_with("a memo", body, web.config, "", [])
                generate.assert_not_called()

    def test_keeps_title_only_state_when_the_memo_is_invalid(self):
        cases = [
            ("  ", "Enter a memo first"),
            ("a" * (web.config.max_input_chars + 1), "The memo is too long"),
        ]
        for text, message in cases:
            with self.subTest(text=repr(text)):
                with mock.patch.object(web, "regenerate_titles") as titles:
                    with mock.patch.object(web, "generate_draft") as generate:
                        answer = self.client.post("/generate", data={
                            "input_text": text,
                            "body": "The settled body",
                            "mode": "titles",
                        })

                page = answer.get_data(as_text=True)
                self.assertEqual(400, answer.status_code)
                self.assertIn(message, page)
                self.assertIn('name="body" value="The settled body"', page)
                self.assertIn('name="mode" value="titles"', page)
                self.assertIn("Regenerate the titles only", page)
                self.assertNotIn('name="mode" value="full"', page)
                titles.assert_not_called()
                generate.assert_not_called()

    def test_keeps_title_regeneration_as_the_retry_mode(self):
        body = "The settled body"
        with mock.patch.object(
                web, "regenerate_titles",
                side_effect=UpstreamTimeoutError()) as titles:
            with mock.patch.object(web, "generate_draft") as generate:
                answer = self.client.post("/generate", data={
                    "input_text": "a memo",
                    "body": body,
                    "mode": "titles",
                })

        page = answer.get_data(as_text=True)
        self.assertEqual(504, answer.status_code)
        self.assertIn('name="body" value="The settled body"', page)
        self.assertIn('name="mode" value="titles"', page)
        self.assertIn("Regenerate the titles only", page)
        self.assertNotIn("Generate once more", page)
        titles.assert_called_once_with("a memo", body, web.config, "", [])
        generate.assert_not_called()

    def test_keeps_full_generation_as_the_retry_mode(self):
        with mock.patch.object(
                web, "generate_draft",
                side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "mode": "full",
            })

        page = answer.get_data(as_text=True)
        self.assertEqual(504, answer.status_code)
        self.assertIn('name="mode" value="full"', page)
        self.assertIn("Generate once more", page)
        self.assertNotIn("Regenerate the titles only", page)

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

    def test_routing_error_pages_have_no_generation_retry_controls(self):
        answer = self.client.get("/nothing-here")

        page = answer.get_data(as_text=True)
        self.assertEqual(404, answer.status_code)
        self.assertNotIn("Generate once more", page)
        self.assertNotIn("Regenerate the titles only", page)
        self.assertNotIn("<textarea", page)

    def test_method_not_allowed_page_has_no_generation_retry_controls(self):
        answer = self.client.post("/healthz")

        page = answer.get_data(as_text=True)
        self.assertEqual(405, answer.status_code)
        self.assertNotIn("Generate once more", page)
        self.assertNotIn("Regenerate the titles only", page)
        self.assertNotIn("<textarea", page)

    def test_still_refuses_an_oversized_request_with_its_own_status(self):
        # The handler for 413 is more specific than the one for every
        # HTTPException, so adding the latter must not shadow it.
        text = "a" * (web.app.config["MAX_CONTENT_LENGTH"] + 1)

        answer = self.client.post("/generate", data={"input_text": text, "mode": "full"})

        self.assertEqual(413, answer.status_code)
        self.assertIn("The request is too large", answer.get_data(as_text=True))

    def test_oversized_request_page_has_no_generation_retry_controls(self):
        text = "a" * (web.app.config["MAX_CONTENT_LENGTH"] + 1)

        answer = self.client.post("/generate", data={"input_text": text, "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(413, answer.status_code)
        self.assertNotIn("Generate once more", page)
        self.assertNotIn("Regenerate the titles only", page)
        self.assertNotIn("<textarea", page)

    def test_still_reports_an_unexpected_failure_as_a_server_error(self):
        with mock.patch.object(web, "generate_draft", side_effect=RuntimeError("boom")):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(500, answer.status_code)
        self.assertIn("The server failed to handle the request", page)
        self.assertNotIn("boom", page)

    def test_unexpected_generation_failure_page_keeps_the_retry_form(self):
        # /generate is where retrying makes sense: an unexpected failure
        # there still offers the same retryable generation form.
        with mock.patch.object(web, "generate_draft", side_effect=RuntimeError("boom")):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(500, answer.status_code)
        self.assertIn("Generate once more", page)

    def test_logs_an_unexpected_failure_once_without_its_raw_message(self):
        with mock.patch.object(
                web, "generate_draft",
                side_effect=RuntimeError("SENSITIVE_MEMO_LIKE_TEXT")):
            with self.assertLogs("app", level=logging.ERROR) as logged:
                answer = self.client.post("/generate", data={
                    "input_text": "a memo", "mode": "full"})

        self.assertEqual(500, answer.status_code)
        self.assertEqual(1, len(logged.output))
        recorded = logged.output[0]
        self.assertIn("type=RuntimeError", recorded)
        self.assertIn("traceback=", recorded)
        self.assertNotIn("SENSITIVE_MEMO_LIKE_TEXT", recorded)
        self.assertNotIn("SENSITIVE_MEMO_LIKE_TEXT", answer.get_data(as_text=True))

    def test_does_not_blame_the_memo_for_a_timeout(self):
        # GENERATION_TIMEOUT is a per-attempt SDK timeout. Its occurrence
        # does not establish that memo length caused the failure, so the
        # user message must not advise shortening the memo.
        with mock.patch.object(web, "generate_draft", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        self.assertNotIn("Shorten the memo", answer.get_data(as_text=True))

    def test_keeps_one_request_reference_through_a_generation_failure(self):
        observed = {}

        def fail_generation(*_args, **_kwargs):
            observed["reference_id"] = get_reference_id()
            raise UpstreamTimeoutError()

        with mock.patch.object(web.secrets, "token_hex", return_value="deadbeef"):
            with mock.patch.object(web, "generate_draft", side_effect=fail_generation):
                with self.assertLogs("app", level=logging.ERROR) as logged:
                    answer = self.client.post("/generate", data={
                        "input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(504, answer.status_code)
        self.assertEqual("deadbeef", observed["reference_id"])
        self.assertIn("(error id: deadbeef)", page)
        self.assertEqual(1, len(logged.output))
        self.assertIn("(reference deadbeef)", logged.output[0])
        self.assertIsNone(get_reference_id())
        self.assertNotIn("Traceback", page)

    def test_input_screen_has_the_character_count_contract(self):
        answer = self.client.get("/")

        self.assertEqual(200, answer.status_code)
        page = answer.get_data(as_text=True)
        self.assertIn(
            'maxlength="{0}"'.format(web.config.max_input_chars), page)
        self.assertIn('data-character-count-target="input-count"', page)
        self.assertIn('id="input-count"', page)

    def test_input_screen_has_the_direction_field_and_count_hook(self):
        answer = self.client.get("/")

        self.assertEqual(200, answer.status_code)
        page = answer.get_data(as_text=True)
        self.assertIn('name="direction"', page)
        self.assertIn("Direction (optional)", page)
        self.assertIn(
            'maxlength="{0}"'.format(web.config.max_policy_chars), page)
        self.assertIn('data-character-count-target="direction-count"', page)
        self.assertIn('id="direction-count"', page)

    def test_generates_normally_with_a_blank_direction(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "direction": "  ", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once_with("a memo", web.config, "")

    def test_passes_a_nonblank_direction_to_full_generation(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "direction": "Keep it short.", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once_with("a memo", web.config, "Keep it short.")

    def test_passes_a_nonblank_direction_to_title_only_regeneration(self):
        with mock.patch.object(
                web, "regenerate_titles", return_value=draft("The settled body")) as titles:
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "body": "The settled body",
                "direction": "Prefer a plain title.",
                "mode": "titles",
            })

        self.assertEqual(200, answer.status_code)
        titles.assert_called_once_with(
            "a memo", "The settled body", web.config, "Prefer a plain title.", [])

    def test_refuses_an_overlong_direction_before_generation(self):
        direction = "a" * (web.config.max_policy_chars + 1)
        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "direction": direction, "mode": "full"})

        self.assertEqual(400, answer.status_code)
        self.assertIn("The direction is too long", answer.get_data(as_text=True))
        generate.assert_not_called()

    def test_preserves_the_direction_across_a_correctable_memo_error(self):
        answer = self.client.post("/generate", data={
            "input_text": "  ", "direction": "Keep it short.", "mode": "full"})

        self.assertEqual(400, answer.status_code)
        page = answer.get_data(as_text=True)
        self.assertIn("Enter a memo first", page)
        self.assertIn("Keep it short.", page)

    def test_preserves_the_direction_across_full_regeneration(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()):
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "direction": "Keep it short.", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        self.assertIn("Keep it short.", answer.get_data(as_text=True))

    def test_preserves_the_direction_across_title_only_regeneration(self):
        with mock.patch.object(
                web, "regenerate_titles", return_value=draft("The settled body")):
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "body": "The settled body",
                "direction": "Prefer a plain title.",
                "mode": "titles",
            })

        self.assertEqual(200, answer.status_code)
        self.assertIn("Prefer a plain title.", answer.get_data(as_text=True))

    def test_preserves_the_direction_on_a_title_only_retry(self):
        with mock.patch.object(
                web, "regenerate_titles", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "body": "The settled body",
                "direction": "Prefer a plain title.",
                "mode": "titles",
            })

        self.assertEqual(504, answer.status_code)
        self.assertIn("Prefer a plain title.", answer.get_data(as_text=True))

    def test_preserves_the_direction_on_a_full_generation_retry(self):
        with mock.patch.object(
                web, "generate_draft", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "direction": "Keep it short.", "mode": "full"})

        self.assertEqual(504, answer.status_code)
        self.assertIn("Keep it short.", answer.get_data(as_text=True))

    def test_result_screen_preserves_existing_notices_as_hidden_fields(self):
        with mock.patch.object(
                web, "generate_draft", return_value=draft(notices=["A notice."])):
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        self.assertIn('name="notice" value="A notice."',
                      answer.get_data(as_text=True))

    def test_title_only_regeneration_passes_existing_notices(self):
        with mock.patch.object(
                web, "regenerate_titles",
                return_value=draft("The settled body")) as titles:
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "body": "The settled body",
                "mode": "titles",
                "notice": ["A notice.", "Another notice."],
            })

        self.assertEqual(200, answer.status_code)
        titles.assert_called_once_with(
            "a memo", "The settled body", web.config, "",
            ["A notice.", "Another notice."])

    def test_title_only_retry_preserves_notices_after_a_failure(self):
        with mock.patch.object(
                web, "regenerate_titles", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "body": "The settled body",
                "mode": "titles",
                "notice": ["A notice."],
            })

        page = answer.get_data(as_text=True)
        self.assertEqual(504, answer.status_code)
        self.assertIn('name="notice" value="A notice."', page)

    def test_correctable_title_only_validation_error_preserves_notices(self):
        answer = self.client.post("/generate", data={
            "input_text": "  ",
            "body": "The settled body",
            "mode": "titles",
            "notice": ["A notice."],
        })

        page = answer.get_data(as_text=True)
        self.assertEqual(400, answer.status_code)
        self.assertIn('name="notice" value="A notice."', page)

    def test_full_regeneration_ignores_submitted_notices(self):
        with mock.patch.object(
                web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={
                "input_text": "a memo",
                "mode": "full",
                "notice": ["A stale notice."],
            })

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once_with("a memo", web.config, "")
        self.assertNotIn("A stale notice.", answer.get_data(as_text=True))

    def test_keeps_the_direction_out_of_the_log(self):
        with mock.patch.object(web, "generate_draft", side_effect=UpstreamTimeoutError()):
            with self.assertLogs("app", level=logging.ERROR) as logged:
                answer = self.client.post("/generate", data={
                    "input_text": "a memo",
                    "direction": "a very particular secret direction",
                    "mode": "full",
                })

        self.assertEqual(504, answer.status_code)
        self.assertNotIn(
            "a very particular secret direction", "\n".join(logged.output))

    def test_starts_a_new_input_screen_with_a_blank_direction(self):
        answer = self.client.get("/")

        page = answer.get_data(as_text=True)
        self.assertIn('name="direction"', page)
        self.assertNotIn("Keep it short.", page)

    def test_clear_button_targets_the_memo_and_direction(self):
        answer = self.client.get("/")

        page = answer.get_data(as_text=True)
        self.assertIn('data-clear-target="input_text direction"', page)

    def test_clear_helper_supports_multiple_targets(self):
        answer = self.client.get("/static/copy.js")

        self.assertEqual(200, answer.status_code)
        script = answer.get_data(as_text=True)
        self.assertIn('getAttribute("data-clear-target")', script)
        self.assertIn('clearTargets.trim().split(/\\s+/)', script)
        self.assertIn("for (var clearIndex = 0", script)
        self.assertIn("updateCharacterCount(field)", script)
        self.assertIn("firstField.focus()", script)

    def test_result_screen_has_memo_limit_and_body_auto_growth_hook(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()):
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        page = answer.get_data(as_text=True)
        self.assertIn("data-auto-grow", page)
        self.assertIn('id="post-body"', page)
        self.assertIn(
            'maxlength="{0}"'.format(web.config.max_input_chars), page)

    def test_web_script_contains_progressive_generation_helpers(self):
        answer = self.client.get("/static/copy.js")

        self.assertEqual(200, answer.status_code)
        script = answer.get_data(as_text=True)
        self.assertIn("data-character-count-target", script)
        self.assertIn("scrollHeight", script)
        self.assertIn('addEventListener("submit"', script)
        self.assertIn("event.submitter", script)
        self.assertIn("data-submitted-button", script)
        self.assertIn("disabled = true", script)
        self.assertIn("data-submitting", script)
        self.assertIn("aria-busy", script)
        self.assertIn("Generating...", script)

    def test_accepts_same_origin_generation_post(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once()

    def test_accepts_same_authority_with_https_origin(self):
        client = web.app.test_client()
        client.environ_base["HTTP_ORIGIN"] = "https://localhost"

        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once()

    def test_refuses_generation_post_without_origin(self):
        client = web.app.test_client()

        with mock.patch.object(
                web, "generate_draft", return_value=draft()) as generate:
            with mock.patch.object(web, "regenerate_titles") as titles:
                answer = client.post("/generate", data={
                    "input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(400, answer.status_code)
        self.assertIn("This request must be submitted from this site.", page)
        generate.assert_not_called()
        titles.assert_not_called()
        self.assertNotIn("a memo", page)
        self.assertNotIn("Generate once more", page)

    def test_refuses_foreign_origin_before_generation(self):
        client = web.app.test_client()
        client.environ_base["HTTP_ORIGIN"] = "https://foreign.example"

        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        self.assertEqual(400, answer.status_code)
        generate.assert_not_called()

    def test_refuses_origin_with_different_port(self):
        client = web.app.test_client()
        client.environ_base["HTTP_ORIGIN"] = "http://localhost:8091"

        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        self.assertEqual(400, answer.status_code)
        generate.assert_not_called()

    def test_refuses_malformed_origins(self):
        origins = (
            "null",
            "file://local",
            "https://localhost/path",
            "https://user@localhost",
            "https://localhost:abc",
            "https://local host",
            "https://localhost?x=1",
            "https://localhost#fragment",
        )
        for origin in origins:
            with self.subTest(origin=origin):
                client = web.app.test_client()
                client.environ_base["HTTP_ORIGIN"] = origin

                with mock.patch.object(
                        web, "generate_draft", return_value=draft()) as generate:
                    answer = client.post("/generate", data={
                        "input_text": "a memo", "mode": "full"})

                self.assertEqual(400, answer.status_code)
                generate.assert_not_called()

    def test_logs_foreign_origin_without_raw_header(self):
        client = web.app.test_client()
        client.environ_base["HTTP_ORIGIN"] = "https://SENSITIVE-FOREIGN-ORIGIN.example"

        with self.assertLogs("app", level=logging.INFO) as logged:
            answer = client.post("/generate", data={
                "input_text": "a memo", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(400, answer.status_code)
        self.assertEqual(1, len(logged.output))
        recorded = logged.output[0]
        self.assertIn("foreign Origin", recorded)
        self.assertNotIn("SENSITIVE-FOREIGN-ORIGIN", recorded)
        self.assertNotIn("SENSITIVE-FOREIGN-ORIGIN", page)

    def test_allows_missing_origin_when_same_origin_check_is_disabled(self):
        client = web.app.test_client()

        with mock.patch.object(web.config, "require_same_origin", False):
            with mock.patch.object(
                    web, "generate_draft", return_value=draft()) as generate:
                answer = client.post("/generate", data={
                    "input_text": "a memo", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once()

    def test_allows_foreign_origin_when_same_origin_check_is_disabled(self):
        client = web.app.test_client()
        client.environ_base["HTTP_ORIGIN"] = "https://foreign.example"

        with mock.patch.object(web.config, "require_same_origin", False):
            with mock.patch.object(
                    web, "generate_draft", return_value=draft()) as generate:
                answer = client.post("/generate", data={
                    "input_text": "a memo", "mode": "full"})

        self.assertEqual(200, answer.status_code)
        generate.assert_called_once()

    def test_origin_check_does_not_change_method_not_allowed_route(self):
        client = web.app.test_client()

        answer = client.post("/healthz")

        self.assertEqual(405, answer.status_code)

    def test_foreign_origin_is_refused_before_oversized_form_parsing(self):
        client = web.app.test_client()
        client.environ_base["HTTP_ORIGIN"] = "https://foreign.example"
        text = "a" * (web.app.config["MAX_CONTENT_LENGTH"] + 1)

        answer = client.post("/generate", data={"input_text": text, "mode": "full"})

        self.assertEqual(400, answer.status_code)


if __name__ == "__main__":
    unittest.main()
