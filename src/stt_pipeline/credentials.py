from __future__ import annotations

import getpass
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from typing import Any


OPENAI_KEYCHAIN_SERVICE = "stt-conference-openai"


def resolve_openai_api_key(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> str | None:
    source = os.environ if environ is None else environ
    environment_key = source.get("OPENAI_API_KEY", "").strip()
    if environment_key:
        return environment_key

    if (platform or sys.platform) != "darwin":
        return None

    account = source.get("USER", "").strip() or getpass.getuser()
    command_runner = runner or subprocess.run
    try:
        result = command_runner(
            [
                "security",
                "find-generic-password",
                "-a",
                account,
                "-s",
                OPENAI_KEYCHAIN_SERVICE,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def build_openai_client(feature: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(f"Install the openai package to use {feature}") from exc

    api_key = resolve_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "Set OPENAI_API_KEY or store the key in macOS Keychain service "
            f"'{OPENAI_KEYCHAIN_SERVICE}'"
        )
    return OpenAI(api_key=api_key)
