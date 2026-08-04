#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import unittest
from unittest import mock

from config import Config
from sizu_writer import generator
from sizu_writer.errors import InvalidResponseError
from sizu_writer.providers import CompletionResult

BODY = {
    "body_markdown": "The body.",
    "primary_title": "The leading title",
    "alternative_titles": ["Another candidate"],
}


def answer(payload, model="served-model"):
    """ Build the CompletionResult a provider would have returned. """
    content = payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False)
    return CompletionResult(content=content, model=model, finish_reason="stop",
                            request_id="resp_1")


def settings(**overrides):
    values = {
        "generation_backend": "openai-compatible",
        "generation_api_token": "uuid:secret",
        "generation_base_url": "https://api.ai.sakura.ad.jp/v1",
        "generation_model": "a-model",
    }
    values.update(overrides)
    return Config(**values)


class GenerateDraftTest(unittest.TestCase):

    def generate(self, result, config=None):
        with mock.patch.object(generator, "build_body_messages", return_value=[]):
            with mock.patch.object(generator, "_complete", return_value=result):
                return generator.generate_draft(
                    "a memo", config if config is not None else settings())

    def test_builds_a_draft_from_a_completion_result(self):
        draft = self.generate(answer(BODY))

        self.assertEqual("The body.", draft.body)
        self.assertEqual("The leading title", draft.primary_title)
        self.assertEqual(["Another candidate"], draft.alternative_titles)
        self.assertEqual("served-model", draft.model)

    def test_names_the_configured_model_when_the_answer_does_not(self):
        draft = self.generate(answer(BODY, model=""))

        self.assertEqual("a-model", draft.model)

    def test_keeps_at_most_max_alt_titles_and_drops_duplicates(self):
        draft = self.generate(answer(dict(BODY, alternative_titles=[
            "The leading title", "", "one", "two", "three", "four", "five"])))

        self.assertEqual(["one", "two", "three", "four"], draft.alternative_titles)

    def test_refuses_an_answer_that_is_not_json(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer("this is not JSON"))

    def test_refuses_an_answer_that_is_json_but_not_an_object(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer("[1, 2, 3]"))

    def test_refuses_an_answer_without_a_body(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer(dict(BODY, body_markdown="  ")))

    def test_refuses_an_answer_without_a_primary_title(self):
        with self.assertRaises(InvalidResponseError):
            self.generate(answer(dict(BODY, primary_title="")))


class ResponseModeTest(unittest.TestCase):
    """
    What each mode accepts.

    json-object trusts the API to have enforced the shape and reads the
    whole answer. prompt-json additionally unwraps a single fenced
    block, because a model asked in words for JSON routinely wraps it.
    Neither mode ever cuts an object out of surrounding prose.
    """

    def payload(self, content, mode):
        return generator._payload(content, mode)

    def test_reads_a_raw_object_in_both_modes(self):
        for mode in ("json-object", "prompt-json"):
            self.assertEqual({"a": 1}, self.payload('{"a": 1}', mode))

    def test_unwraps_a_single_fenced_block_under_prompt_json(self):
        content = '```json\n{"a": 1}\n```'

        self.assertEqual({"a": 1}, self.payload(content, "prompt-json"))

    def test_unwraps_a_fence_without_an_info_string(self):
        content = '```\n{"a": 1}\n```'

        self.assertEqual({"a": 1}, self.payload(content, "prompt-json"))

    def test_refuses_a_fenced_block_under_json_object(self):
        # The API was told to answer with an object. A fence means it
        # did not, and accepting it here would hide the misconfiguration.
        with self.assertRaises(InvalidResponseError):
            self.payload('```json\n{"a": 1}\n```', "json-object")

    def test_refuses_prose_before_a_fenced_block(self):
        content = 'Here is the result.\n\n```json\n{"a": 1}\n```'

        with self.assertRaises(InvalidResponseError):
            self.payload(content, "prompt-json")

    def test_refuses_prose_after_a_fenced_block(self):
        content = '```json\n{"a": 1}\n```\n\nLet me know what you think.'

        with self.assertRaises(InvalidResponseError):
            self.payload(content, "prompt-json")

    def test_refuses_an_object_surrounded_by_prose(self):
        with self.assertRaises(InvalidResponseError):
            self.payload('Some words\n{"a": 1}\nmore words', "prompt-json")

    def test_extracts_no_fragment_of_a_larger_answer(self):
        # The first '{' and the last '}' of this answer delimit valid
        # JSON. Reading it would be the heuristic this design refuses.
        content = 'Result: {"a": 1} and that is all.'

        with self.assertRaises(InvalidResponseError):
            self.payload(content, "prompt-json")


class RegenerateTitlesTest(unittest.TestCase):

    def test_keeps_the_body_it_was_given(self):
        result = answer({"primary_title": "A new leading title",
                         "alternative_titles": []})

        with mock.patch.object(generator, "build_titles_messages", return_value=[]):
            with mock.patch.object(generator, "_complete", return_value=result):
                draft = generator.regenerate_titles(
                    "a memo", "The settled body", settings())

        self.assertEqual("The settled body", draft.body)
        self.assertEqual("A new leading title", draft.primary_title)

    def test_reads_a_fenced_answer_under_prompt_json(self):
        result = answer('```json\n{"primary_title": "A new leading title", '
                        '"alternative_titles": []}\n```')

        with mock.patch.object(generator, "build_titles_messages", return_value=[]):
            with mock.patch.object(generator, "_complete", return_value=result):
                draft = generator.regenerate_titles(
                    "a memo", "The settled body", settings())

        self.assertEqual("A new leading title", draft.primary_title)


class CompleteTest(unittest.TestCase):

    def test_spends_one_request_through_the_configured_provider(self):
        provider = mock.Mock()
        provider.complete.return_value = answer(BODY)
        config = settings()

        with mock.patch.object(generator, "build_provider", return_value=provider):
            with mock.patch.object(generator, "build_body_messages",
                                   return_value=[{"role": "user", "content": "x"}]):
                generator.generate_draft("a memo", config)

        provider.complete.assert_called_once_with(
            [{"role": "user", "content": "x"}], config)


if __name__ == "__main__":
    unittest.main()
