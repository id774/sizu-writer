#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
from unittest import mock

import config

# A configuration that passes validate_generation_config(), used as the
# base of the cases that break exactly one of its values.
COMPLETE = {
    "GENERATION_BACKEND": "openai-compatible",
    "GENERATION_API_TOKEN": "00000000-0000-0000-0000-000000000000:secret",
    "GENERATION_BASE_URL": "https://api.ai.sakura.ad.jp/v1",
    "GENERATION_MODEL": "a-model",
}


class LoadConfigTest(unittest.TestCase):

    def load(self, environment):
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch.object(config, "load_dotenv", None):
                return config.load_config()

    def refuse(self, environment):
        with self.assertRaises(config.ConfigError) as refused:
            self.load(environment)
        return str(refused.exception)

    def test_uses_the_documented_defaults(self):
        loaded = self.load({})

        self.assertEqual("prompt-json", loaded.generation_response_mode)
        self.assertEqual(60.0, loaded.generation_timeout)
        self.assertEqual(6000, loaded.max_output_tokens)
        self.assertEqual(4000, loaded.max_input_chars)
        self.assertEqual(4, loaded.max_alt_titles)
        self.assertEqual("prompts", loaded.prompt_dir)
        self.assertEqual(8090, loaded.port)

    def test_spends_one_request_unless_told_otherwise(self):
        self.assertEqual(0, self.load({}).generation_max_retries)

    def test_treats_a_blank_value_as_unset(self):
        loaded = self.load({"PROMPT_DIR": "   ", "GENERATION_TIMEOUT": ""})

        self.assertEqual("prompts", loaded.prompt_dir)
        self.assertEqual(60.0, loaded.generation_timeout)

    def test_sends_no_temperature_unless_it_is_set(self):
        self.assertIsNone(self.load({}).generation_temperature)
        self.assertEqual(
            0.7, self.load({"GENERATION_TEMPERATURE": "0.7"}).generation_temperature)

    def test_refuses_a_value_that_is_not_a_number(self):
        message = self.refuse({"GENERATION_TIMEOUT": "soon"})

        self.assertIn("GENERATION_TIMEOUT", message)
        self.assertIn("soon", message)

    def test_names_the_setting_when_the_temperature_is_not_a_number(self):
        self.assertIn("GENERATION_TEMPERATURE",
                      self.refuse({"GENERATION_TEMPERATURE": "warm"}))

    def test_refuses_a_timeout_that_is_not_positive(self):
        self.assertIn("GENERATION_TIMEOUT",
                      self.refuse({"GENERATION_TIMEOUT": "0"}))

    def test_refuses_a_negative_retry_count(self):
        message = self.refuse({"GENERATION_MAX_RETRIES": "-1"})

        self.assertIn("GENERATION_MAX_RETRIES", message)
        self.assertIn("-1", message)

    def test_refuses_an_unknown_response_mode(self):
        message = self.refuse({"GENERATION_RESPONSE_MODE": "auto"})

        self.assertIn("auto", message)
        self.assertIn("json-object", message)
        self.assertIn("prompt-json", message)

    def test_refuses_an_output_limit_of_zero(self):
        self.assertIn("MAX_OUTPUT_TOKENS",
                      self.refuse({"MAX_OUTPUT_TOKENS": "0"}))

    def test_refuses_a_port_outside_the_range(self):
        self.assertIn("PORT", self.refuse({"PORT": "70000"}))

    def test_hides_the_api_token_from_repr(self):
        loaded = self.load({"GENERATION_API_TOKEN": "uuid:secret-value"})

        self.assertEqual("uuid:secret-value", loaded.generation_api_token)
        self.assertNotIn("secret-value", repr(loaded))

    def test_reports_the_host_of_the_base_url(self):
        loaded = self.load({"GENERATION_BASE_URL": "https://api.ai.sakura.ad.jp/v1"})

        self.assertEqual("api.ai.sakura.ad.jp", loaded.endpoint_host)


class LegacyVariableTest(unittest.TestCase):
    """ v1.x settings are refused, never translated. """

    def refuse(self, environment):
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch.object(config, "load_dotenv", None):
                with self.assertRaises(config.ConfigError) as refused:
                    config.load_config()
        return str(refused.exception)

    def test_refuses_every_legacy_variable_by_name(self):
        for legacy, replacement in config.LEGACY_VARIABLES.items():
            message = self.refuse(dict(COMPLETE, **{legacy: "whatever"}))

            self.assertIn(legacy, message)
            self.assertIn(replacement, message)

    def test_refuses_a_legacy_variable_that_is_exported_but_empty(self):
        # An exported OPENAI_BASE_URL says the host was set up for v1,
        # whatever it holds. Reading it as unset would let v1.x and
        # v2.0 settings coexist and decide the endpoint between them.
        self.assertIn("OPENAI_BASE_URL",
                      self.refuse(dict(COMPLETE, OPENAI_BASE_URL="")))

    def test_keeps_the_legacy_value_out_of_the_message(self):
        message = self.refuse(dict(COMPLETE, OPENAI_API_KEY="sk-secret-value"))

        self.assertNotIn("sk-secret-value", message)


class ValidateGenerationConfigTest(unittest.TestCase):

    def config(self, **overrides):
        settings = {
            "generation_backend": "openai-compatible",
            "generation_api_token": "uuid:secret",
            "generation_base_url": "https://api.ai.sakura.ad.jp/v1",
            "generation_model": "a-model",
        }
        settings.update(overrides)
        return config.Config(**settings)

    def refuse(self, **overrides):
        with self.assertRaises(config.ConfigError) as refused:
            config.validate_generation_config(self.config(**overrides))
        return str(refused.exception)

    def test_accepts_a_complete_configuration(self):
        self.assertIsNone(config.validate_generation_config(self.config()))

    def test_refuses_a_missing_backend(self):
        self.assertIn("GENERATION_BACKEND", self.refuse(generation_backend=""))

    def test_refuses_an_unknown_backend(self):
        message = self.refuse(generation_backend="sakura")

        self.assertIn("sakura", message)
        self.assertIn("openai-compatible", message)

    def test_refuses_a_missing_token(self):
        self.assertIn("GENERATION_API_TOKEN",
                      self.refuse(generation_api_token=""))

    def test_refuses_a_token_carrying_a_line_break(self):
        message = self.refuse(generation_api_token="uuid:sec\nret")

        self.assertIn("GENERATION_API_TOKEN", message)
        self.assertNotIn("uuid:sec", message)

    def test_refuses_a_missing_base_url(self):
        self.assertIn("GENERATION_BASE_URL", self.refuse(generation_base_url=""))

    def test_refuses_a_plain_http_base_url(self):
        message = self.refuse(generation_base_url="http://api.example.net/v1")

        self.assertIn("https", message)

    def test_refuses_a_relative_base_url(self):
        self.assertIn("GENERATION_BASE_URL",
                      self.refuse(generation_base_url="api.example.net/v1"))

    def test_refuses_a_base_url_carrying_user_information(self):
        self.assertIn("user information",
                      self.refuse(generation_base_url="https://user:pw@api.example.net/v1"))

    def test_refuses_a_base_url_carrying_a_query(self):
        self.assertIn("query",
                      self.refuse(generation_base_url="https://api.example.net/v1?key=x"))

    def test_refuses_a_base_url_holding_the_resource_path(self):
        message = self.refuse(
            generation_base_url="https://api.ai.sakura.ad.jp/v1/chat/completions")

        self.assertIn("/chat/completions", message)

    def test_refuses_a_missing_model(self):
        self.assertIn("GENERATION_MODEL", self.refuse(generation_model=""))

    def test_keeps_the_token_out_of_every_message(self):
        for overrides in ({"generation_backend": "sakura"},
                          {"generation_base_url": "http://api.example.net/v1"},
                          {"generation_model": ""}):
            self.assertNotIn("uuid:secret", self.refuse(**overrides))


if __name__ == "__main__":
    unittest.main()
