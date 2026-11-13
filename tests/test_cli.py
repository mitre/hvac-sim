import argparse
import unittest

from simulator.cli import add_deprecated_alias, warn_deprecated


class DeprecatedAliasTests(unittest.TestCase):
    def setUp(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument("--host", default="127.0.0.1")
        add_deprecated_alias(self.parser, "--device-ip", "--host")

    def test_alias_sets_the_new_flag(self):
        args = self.parser.parse_args(["--device-ip", "10.0.0.5"])
        self.assertEqual(args.host, "10.0.0.5")

    def test_default_is_kept_without_the_alias(self):
        args = self.parser.parse_args([])
        self.assertEqual(args.host, "127.0.0.1")

    def test_alias_logs_one_warning(self):
        args = self.parser.parse_args(["--device-ip", "10.0.0.5", "--device-ip", "10.0.0.6"])
        with self.assertLogs("simulator.cli", level="WARNING") as logs:
            warn_deprecated(args)
        self.assertEqual(logs.output, ["WARNING:simulator.cli:--device-ip is deprecated, use --host"])

    def test_new_flag_logs_nothing(self):
        args = self.parser.parse_args(["--host", "10.0.0.5"])
        with self.assertNoLogs("simulator.cli", level="WARNING"):
            warn_deprecated(args)

    def test_alias_is_hidden_from_help(self):
        self.assertNotIn("--device-ip", self.parser.format_help())
