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
                return generator.generate_draft("メモ", self.config)

    def test_builds_a_draft_from_a_well_formed_answer(self):
        draft = self.generate(answer({
            "body_markdown": "本文です。",
            "primary_title": "第一候補",
            "alternative_titles": ["別案"],
        }))

        self.assertEqual("本文です。", draft.body)
        self.assertEqual("第一候補", draft.primary_title)
        self.assertEqual(["別案"], draft.alternative_titles)
        self.assertEqual("test-model", draft.model)

    def test_keeps_at_most_max_alt_titles_and_drops_duplicates(self):
        draft = self.generate(answer({
            "body_markdown": "本文です。",
            "primary_title": "第一候補",
            "alternative_titles": ["第一候補", "", "案 1", "案 2", "案 3", "案 4", "案 5"],
        }))

        self.assertEqual(["案 1", "案 2", "案 3", "案 4"], draft.alternative_titles)

    def test_refuses_an_answer_that_is_not_json(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer("これは JSON ではありません"))

    def test_refuses_an_answer_without_a_body(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer({"body_markdown": "  ", "primary_title": "第一候補",
                                  "alternative_titles": []}))

    def test_refuses_an_answer_that_was_cut_off(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer({"body_markdown": "本文です。", "primary_title": "第一候補",
                                  "alternative_titles": []}, finish_reason="length"))


class RegenerateTitlesTest(unittest.TestCase):

    def test_keeps_the_body_it_was_given(self):
        config = Config(openai_api_key="key", openai_model="test-model")
        response = answer({"primary_title": "新しい第一候補", "alternative_titles": []})

        with mock.patch.object(generator, "build_titles_messages", return_value=[]):
            with mock.patch.object(generator, "_complete", return_value=response):
                draft = generator.regenerate_titles("メモ", "既存の本文", config)

        self.assertEqual("既存の本文", draft.body)
        self.assertEqual("新しい第一候補", draft.primary_title)


if __name__ == "__main__":
    unittest.main()
