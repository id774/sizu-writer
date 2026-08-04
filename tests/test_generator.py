#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import unittest
from types import SimpleNamespace
from unittest import mock

from config import Config
from sizu_writer import generator
from sizu_writer.errors import InvalidResponseError


def answer(payload, finish_reason="stop"):
    content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test-model")


class GenerateDraftTest(unittest.TestCase):

    def setUp(self):
        self.config = Config(openai_api_key="key", openai_model="test-model")

    def generate(self, response):
        with mock.patch.object(generator, "build_body_messages", return_value=[]):
            with mock.patch.object(generator, "_complete", return_value=response):
                return generator.generate_draft("a memo", self.config)

    def test_builds_a_draft_from_a_well_formed_answer(self):
        draft = self.generate(answer({
            "body_markdown": "The body.",
            "primary_title": "The leading title",
            "alternative_titles": ["Another candidate"],
        }))

        self.assertEqual("The body.", draft.body)
        self.assertEqual("The leading title", draft.primary_title)
        self.assertEqual(["Another candidate"], draft.alternative_titles)
        self.assertEqual("test-model", draft.model)

    def test_keeps_at_most_max_alt_titles_and_drops_duplicates(self):
        draft = self.generate(answer({
            "body_markdown": "The body.",
            "primary_title": "The leading title",
            "alternative_titles": ["The leading title", "", "one", "two", "three", "four", "five"],
        }))

        self.assertEqual(["one", "two", "three", "four"], draft.alternative_titles)

    def test_refuses_an_answer_that_is_not_json(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer("this is not JSON"))

    def test_refuses_an_answer_without_a_body(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer({"body_markdown": "  ", "primary_title": "The leading title",
                                  "alternative_titles": []}))

    def test_refuses_an_answer_that_was_cut_off(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer({"body_markdown": "The body.", "primary_title": "The leading title",
                                  "alternative_titles": []}, finish_reason="length"))


class RegenerateTitlesTest(unittest.TestCase):

    def test_keeps_the_body_it_was_given(self):
        config = Config(openai_api_key="key", openai_model="test-model")
        response = answer({"primary_title": "A new leading title", "alternative_titles": []})

        with mock.patch.object(generator, "build_titles_messages", return_value=[]):
            with mock.patch.object(generator, "_complete", return_value=response):
                draft = generator.regenerate_titles("a memo", "The settled body", config)

        self.assertEqual("The settled body", draft.body)
        self.assertEqual("A new leading title", draft.primary_title)


if __name__ == "__main__":
    unittest.main()
