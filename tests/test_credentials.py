import subprocess
import unittest

from stt_pipeline.credentials import OPENAI_KEYCHAIN_SERVICE, resolve_openai_api_key


class CredentialsTest(unittest.TestCase):
    def test_environment_key_takes_priority_without_keychain_lookup(self):
        def fail_runner(*args, **kwargs):
            raise AssertionError("Keychain should not be queried")

        key = resolve_openai_api_key(
            environ={"OPENAI_API_KEY": " env-secret ", "USER": "tester"},
            platform="darwin",
            runner=fail_runner,
        )

        self.assertEqual(key, "env-secret")

    def test_macos_falls_back_to_named_keychain_item(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=" keychain-secret\n",
                stderr="",
            )

        key = resolve_openai_api_key(
            environ={"USER": "tester"},
            platform="darwin",
            runner=fake_runner,
        )

        self.assertEqual(key, "keychain-secret")
        self.assertEqual(
            calls[0][0],
            [
                "security",
                "find-generic-password",
                "-a",
                "tester",
                "-s",
                OPENAI_KEYCHAIN_SERVICE,
                "-w",
            ],
        )
        self.assertTrue(calls[0][1]["capture_output"])

    def test_non_macos_without_environment_key_returns_none(self):
        key = resolve_openai_api_key(environ={}, platform="linux")

        self.assertIsNone(key)

    def test_failed_keychain_lookup_returns_none(self):
        def fake_runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 44, stdout="", stderr="not found")

        key = resolve_openai_api_key(
            environ={"USER": "tester"},
            platform="darwin",
            runner=fake_runner,
        )

        self.assertIsNone(key)


if __name__ == "__main__":
    unittest.main()
