#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
from unittest import mock

import config


class LoadConfigTest(unittest.TestCase):

    def load(self, environment):
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch.object(config, "load_dotenv", None):
                return config.load_config()

    def test_uses_the_documented_defaults(self):
        loaded = self.load({})

        self.assertEqual(60.0, loaded.openai_timeout)
        self.assertEqual(2, loaded.openai_max_retries)
        self.assertEqual(4, loaded.max_alt_titles)
        self.assertEqual("prompts", loaded.prompt_dir)
        self.assertEqual(8090, loaded.port)

    def test_treats_a_blank_value_as_unset(self):
        loaded = self.load({"PROMPT_DIR": "   ", "OPENAI_TIMEOUT": ""})

        self.assertEqual("prompts", loaded.prompt_dir)
        self.assertEqual(60.0, loaded.openai_timeout)

    def test_sends_no_temperature_unless_it_is_set(self):
        self.assertIsNone(self.load({}).openai_temperature)
        self.assertEqual(0.7, self.load({"OPENAI_TEMPERATURE": "0.7"}).openai_temperature)

    def test_refuses_a_value_that_is_not_a_number(self):
        with self.assertRaises(ValueError):
            self.load({"OPENAI_TIMEOUT": "soon"})

    def test_hides_the_api_key_from_repr(self):
        loaded = self.load({"OPENAI_API_KEY": "sk-secret-value"})

        self.assertEqual("sk-secret-value", loaded.openai_api_key)
        self.assertNotIn("sk-secret-value", repr(loaded))


if __name__ == "__main__":
    unittest.main()
