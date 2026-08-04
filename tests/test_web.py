#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
from unittest import mock

# app.py validates the generation settings while it is imported, so a
# worker that cannot address an endpoint refuses to start. These values
# are what that check needs and nothing more: no request is ever made,
# and setdefault leaves a real .env alone when one is present.
os.environ.setdefault("GENERATION_BACKEND", "openai-compatible")
os.environ.setdefault("GENERATION_API_TOKEN", "test-token")
os.environ.setdefault("GENERATION_BASE_URL", "https://api.example.test/v1")
os.environ.setdefault("GENERATION_MODEL", "test-model")

import app as web  # noqa: E402  imported after the settings above
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

    def test_does_not_blame_the_memo_for_a_timeout(self):
        # The wait is the answer being written, not the memo being read.
        # A one line memo asks for the same post as a long one, so advice
        # to shorten it sends the person editing while nothing changes.
        with mock.patch.object(web, "generate_draft", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={"input_text": "a memo", "mode": "full"})

        self.assertNotIn("Shorten the memo", answer.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
