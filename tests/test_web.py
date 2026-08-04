#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from unittest import mock

import app as web
from sizu_writer import Draft
from sizu_writer.errors import UpstreamTimeoutError


def draft(body="本文です。"):
    return Draft(
        body=body,
        primary_title="第一候補",
        alternative_titles=["別案"],
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
        text = "あ" * (web.config.max_input_chars + 1)

        answer = self.client.post("/generate", data={"input_text": text, "mode": "full"})

        self.assertEqual(400, answer.status_code)
        self.assertIn("入力が長すぎます", answer.get_data(as_text=True))
        self.assertIn(text, answer.get_data(as_text=True))

    def test_refuses_an_empty_input(self):
        answer = self.client.post("/generate", data={"input_text": "  ", "mode": "full"})

        self.assertEqual(400, answer.status_code)
        self.assertIn("短文を入力してください", answer.get_data(as_text=True))

    def test_shows_the_body_and_the_titles_of_a_draft(self):
        with mock.patch.object(web, "generate_draft", return_value=draft()) as generate:
            answer = self.client.post("/generate", data={"input_text": "メモ", "mode": "full"})

        generate.assert_called_once()
        page = answer.get_data(as_text=True)
        self.assertIn("本文です。", page)
        self.assertIn("第一候補", page)
        self.assertIn("別案", page)

    def test_regenerates_the_titles_of_the_body_it_was_given(self):
        with mock.patch.object(web, "regenerate_titles", return_value=draft("既存の本文")) as titles:
            with mock.patch.object(web, "generate_draft") as generate:
                answer = self.client.post("/generate", data={
                    "input_text": "メモ", "body": "既存の本文", "mode": "titles"})

        generate.assert_not_called()
        titles.assert_called_once()
        self.assertIn("既存の本文", answer.get_data(as_text=True))

    def test_hides_the_cause_of_a_generation_failure(self):
        with mock.patch.object(web, "generate_draft", side_effect=UpstreamTimeoutError()):
            answer = self.client.post("/generate", data={"input_text": "メモ", "mode": "full"})

        page = answer.get_data(as_text=True)
        self.assertEqual(504, answer.status_code)
        self.assertIn("時間がかかりすぎた", page)
        self.assertNotIn("Traceback", page)


if __name__ == "__main__":
    unittest.main()
