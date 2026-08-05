#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################################
# tests/test_openai_compatible_provider.py: Tests for the OpenAI compatible provider
#
#  Description:
#  This test suite covers the one provider the application ships with.
#  It pins what reaches the SDK, namely the token, the base URL, the
#  retry count and the timeout on the client, and the model, the
#  messages, the output limit, the response format per mode and the
#  temperature on the request. It covers the normalization of an answer
#  into a CompletionResult, the refusal of an answer that carries no
#  usable content, and the mapping of a timeout, a connection failure
#  and an error status onto the error hierarchy.
#
#  The openai package is never imported. A stand-in module is installed
#  in sys.modules for the duration of a call, so the suite needs neither
#  the dependency nor a network. Its exception classes are defined once
#  at module level rather than per call, because the provider catches
#  them by identity.
#
#  The log cases are part of the contract rather than an extra: a line
#  records the shape of an exchange and never its content, and the
#  elapsed seconds appear next to the limit on a success and on a
#  timeout alike, because only that pair says whether the limit was
#  reached or the connection died well short of it.
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
#      python -m unittest tests.test_openai_compatible_provider
#
#  Test Cases:
#    - Hand the token and the base URL to the SDK.
#    - Pass the base URL even when it is empty, so the SDK never falls back.
#    - Spend one request by default, with the configured timeout.
#    - Send the model, the messages and the output limit.
#    - Ask for a JSON object under json-object mode.
#    - Send no response format under prompt-json mode.
#    - Send no temperature unless it is set, and send it when it is.
#    - Never stream.
#    - Normalize a well formed answer, including the usage counters.
#    - Measure how long the one request took.
#    - Accept an answer that carries no usage.
#    - Fall back to the configured model name when the answer names none.
#    - Refuse an answer without a choice.
#    - Refuse an empty content, and a content that is not a string.
#    - Refuse an answer cut off by the output limit.
#    - Map a timeout onto UpstreamTimeoutError.
#    - Map a connection failure onto UpstreamConnectionError.
#    - Map 401, 403, 429 and 500 onto one user facing error.
#    - Record the shape of an answer without its content or the token.
#    - Record the wait next to the limit on an answer and on a timeout.
#    - Keep the token out of a failure line.
#
#  Requirements:
#  - Python Version: 3.9 or later
#  - Standard library only (the openai package is stubbed, never imported)
#
#  Version History:
#  v1.0 2026-08-05
#       Initial release.
#
########################################################################

import logging
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest import mock

from config import Config
from sizu_writer.errors import (InvalidResponseError, UpstreamConnectionError,
                                UpstreamStatusError, UpstreamTimeoutError)
from sizu_writer.providers.openai_compatible import OpenAICompatibleProvider

TOKEN = "00000000-0000-0000-0000-000000000000:secret-value"


class FakeError(Exception):
    """ Base of the exception classes the fake SDK raises. """


class FakeTimeoutError(FakeError):
    """ Stands in for openai.APITimeoutError. """


class FakeConnectionError(FakeError):
    """ Stands in for openai.APIConnectionError. """


class FakeStatusError(FakeError):
    """ Stands in for openai.APIStatusError. """

    def __init__(self, status_code):
        super().__init__("status {0}".format(status_code))
        self.status_code = status_code
        self.request_id = "req_1"


def fake_openai(response=None, error=None):
    """
    Build a stand-in for the openai package.

    The real one is never imported, so the suite needs neither the
    dependency nor a network. The exception classes are defined once at
    module level rather than per call, because the provider catches
    them by identity: a class rebuilt for each fake module would never
    match the one an instance was raised from.
    """
    module = ModuleType("openai")
    module.APIError = FakeError
    module.APITimeoutError = FakeTimeoutError
    module.APIConnectionError = FakeConnectionError
    module.APIStatusError = FakeStatusError

    calls = {}

    def create(**request):
        calls["request"] = request
        if error is not None:
            raise error
        return response

    def client(**options):
        calls["options"] = options
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    module.OpenAI = client
    module.calls = calls
    return module


def answer(content="{}", finish_reason="stop", usage=None, model="served-model",
           identifier="resp_1", choices=None):
    message = SimpleNamespace(content=content)
    if choices is None:
        choices = [SimpleNamespace(message=message, finish_reason=finish_reason)]
    return SimpleNamespace(choices=choices, model=model, id=identifier,
                           usage=usage)


def settings(**overrides):
    values = {
        "generation_backend": "openai-compatible",
        "generation_api_token": TOKEN,
        "generation_base_url": "https://api.ai.sakura.ad.jp/v1",
        "generation_model": "a-model",
    }
    values.update(overrides)
    return Config(**values)


class ProviderTest(unittest.TestCase):

    def complete(self, module, config=None, messages=None):
        with mock.patch.dict(sys.modules, {"openai": module}):
            return OpenAICompatibleProvider().complete(
                messages if messages is not None else [{"role": "user", "content": "x"}],
                config if config is not None else settings())

    def raise_from_sdk(self, error):
        """ Let the SDK fail with the given error during one call. """
        module = fake_openai(error=error)
        with mock.patch.dict(sys.modules, {"openai": module}):
            OpenAICompatibleProvider().complete([], settings())


class ClientTest(ProviderTest):

    def test_hands_the_token_and_the_base_url_to_the_sdk(self):
        module = fake_openai(answer())

        self.complete(module)

        self.assertEqual(TOKEN, module.calls["options"]["api_key"])
        self.assertEqual("https://api.ai.sakura.ad.jp/v1",
                         module.calls["options"]["base_url"])

    def test_passes_the_base_url_even_when_it_is_empty(self):
        # config.py refuses an empty one, but the SDK must never be
        # left to fall back to the endpoint compiled into it.
        module = fake_openai(answer())

        self.complete(module, settings(generation_base_url=""))

        self.assertIn("base_url", module.calls["options"])

    def test_spends_one_request_by_default(self):
        module = fake_openai(answer())

        self.complete(module)

        self.assertEqual(0, module.calls["options"]["max_retries"])
        self.assertEqual(120.0, module.calls["options"]["timeout"])


class RequestTest(ProviderTest):

    def test_sends_the_model_the_messages_and_the_output_limit(self):
        module = fake_openai(answer())
        messages = [{"role": "system", "content": "policy"}]

        self.complete(module, settings(max_output_tokens=1234), messages)

        self.assertEqual("a-model", module.calls["request"]["model"])
        self.assertEqual(messages, module.calls["request"]["messages"])
        self.assertEqual(1234, module.calls["request"]["max_tokens"])

    def test_asks_for_a_json_object_in_that_mode(self):
        module = fake_openai(answer())

        self.complete(module, settings(generation_response_mode="json-object"))

        self.assertEqual({"type": "json_object"},
                         module.calls["request"]["response_format"])

    def test_sends_no_response_format_under_prompt_json(self):
        module = fake_openai(answer())

        self.complete(module, settings(generation_response_mode="prompt-json"))

        self.assertNotIn("response_format", module.calls["request"])

    def test_sends_no_temperature_unless_it_is_set(self):
        module = fake_openai(answer())

        self.complete(module)

        self.assertNotIn("temperature", module.calls["request"])

    def test_sends_the_temperature_when_it_is_set(self):
        module = fake_openai(answer())

        self.complete(module, settings(generation_temperature=0.3))

        self.assertEqual(0.3, module.calls["request"]["temperature"])

    def test_never_streams(self):
        module = fake_openai(answer())

        self.complete(module)

        self.assertNotIn("stream", module.calls["request"])


class ResponseTest(ProviderTest):

    def test_normalizes_a_well_formed_answer(self):
        usage = SimpleNamespace(prompt_tokens=11, completion_tokens=22,
                                total_tokens=33)
        module = fake_openai(answer(content="{\"a\": 1}", usage=usage))

        result = self.complete(module)

        self.assertEqual("{\"a\": 1}", result.content)
        self.assertEqual("served-model", result.model)
        self.assertEqual("stop", result.finish_reason)
        self.assertEqual("resp_1", result.request_id)
        self.assertEqual(11, result.prompt_tokens)
        self.assertEqual(22, result.completion_tokens)
        self.assertEqual(33, result.total_tokens)

    def test_measures_how_long_the_one_request_took(self):
        result = self.complete(fake_openai(answer(content="{}")))

        self.assertIsNotNone(result.elapsed_seconds)
        self.assertGreaterEqual(result.elapsed_seconds, 0.0)

    def test_accepts_an_answer_without_usage(self):
        result = self.complete(fake_openai(answer(content="{}", usage=None)))

        self.assertIsNone(result.prompt_tokens)
        self.assertIsNone(result.total_tokens)

    def test_falls_back_to_the_configured_model_name(self):
        result = self.complete(fake_openai(answer(content="{}", model=None)))

        self.assertEqual("a-model", result.model)

    def test_refuses_an_answer_without_a_choice(self):
        with self.assertRaises(InvalidResponseError):
            self.complete(fake_openai(answer(choices=[])))

    def test_refuses_an_empty_content(self):
        with self.assertRaises(InvalidResponseError):
            self.complete(fake_openai(answer(content="   ")))

    def test_refuses_a_content_that_is_not_a_string(self):
        with self.assertRaises(InvalidResponseError):
            self.complete(fake_openai(answer(content=None)))

    def test_refuses_an_answer_cut_off_by_the_output_limit(self):
        for reason in ("length", "max_tokens"):
            with self.assertRaises(InvalidResponseError):
                self.complete(fake_openai(answer(content="{}", finish_reason=reason)))


class FailureTest(ProviderTest):

    def test_maps_a_timeout(self):
        with self.assertRaises(UpstreamTimeoutError):
            self.raise_from_sdk(FakeTimeoutError("too slow"))

    def test_maps_a_connection_failure(self):
        with self.assertRaises(UpstreamConnectionError):
            self.raise_from_sdk(FakeConnectionError("unreachable"))

    def test_maps_every_error_status_to_one_user_facing_error(self):
        # 401, 403, 429 and 500 differ in the log and nowhere else: a
        # screen naming the difference would report the configuration
        # of the server to whoever asked for a draft.
        for status in (401, 403, 429, 500):
            with self.assertRaises(UpstreamStatusError):
                self.raise_from_sdk(FakeStatusError(status))


class LogTest(ProviderTest):

    def test_records_the_shape_of_an_answer_without_its_content(self):
        usage = SimpleNamespace(prompt_tokens=11, completion_tokens=22,
                                total_tokens=33)
        module = fake_openai(answer(content="{\"body_markdown\": \"secret text\"}",
                                    usage=usage))

        with self.assertLogs("sizu_writer.providers", level=logging.INFO) as logged:
            self.complete(module)

        recorded = "\n".join(logged.output)
        self.assertIn("endpoint_host=api.ai.sakura.ad.jp", recorded)
        self.assertIn("request_id=resp_1", recorded)
        self.assertIn("model=served-model", recorded)
        self.assertNotIn(TOKEN, recorded)
        self.assertNotIn("secret text", recorded)

    def test_records_the_wait_next_to_the_limit_on_an_answer(self):
        module = fake_openai(answer(content="{}"))

        with self.assertLogs("sizu_writer.providers", level=logging.INFO) as logged:
            self.complete(module, settings(generation_timeout=120.0))

        recorded = "\n".join(logged.output)
        self.assertIn("elapsed=", recorded)
        self.assertIn("timeout=120.0", recorded)

    def test_records_the_wait_of_a_timeout_next_to_the_limit(self):
        # Without the elapsed seconds a timeout line cannot say whether
        # the limit was reached or the connection died well short of it,
        # and only one of the two is answered by raising the limit.
        with self.assertLogs("sizu_writer.providers.openai_compatible",
                             level=logging.ERROR) as logged:
            with self.assertRaises(UpstreamTimeoutError):
                self.raise_from_sdk(FakeTimeoutError("too slow"))

        recorded = "\n".join(logged.output)
        self.assertIn("elapsed=", recorded)
        self.assertIn("timeout=120.0", recorded)

    def test_keeps_the_token_out_of_a_failure_line(self):
        with self.assertLogs("sizu_writer.providers.openai_compatible",
                             level=logging.ERROR) as logged:
            with self.assertRaises(UpstreamStatusError):
                self.raise_from_sdk(FakeStatusError(401))

        recorded = "\n".join(logged.output)
        self.assertIn("status=401", recorded)
        self.assertNotIn(TOKEN, recorded)


if __name__ == "__main__":
    unittest.main()
