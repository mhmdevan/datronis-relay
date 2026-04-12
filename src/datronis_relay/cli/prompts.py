"""Abstract prompt interface so the setup wizard is fully testable.

The real `CliPrompter` wraps `input()` and `getpass.getpass()`. Tests use
a scripted fake that returns preset answers without touching stdin.
"""

from __future__ import annotations

import getpass
from collections.abc import Iterator
from typing import Protocol


class Prompter(Protocol):
    """Abstract prompt interface the setup wizard depends on."""

    def say(self, message: str) -> None: ...

    def ask(self, question: str, default: str = "") -> str: ...

    def ask_secret(self, question: str) -> str: ...

    def ask_choice(self, question: str, choices: list[str], default: int = 0) -> int: ...

    def confirm(self, question: str, default: bool = False) -> bool: ...


class CliPrompter:
    """Real interactive prompter using `input()` + `getpass.getpass()`."""

    def say(self, message: str) -> None:
        print(message)

    def ask(self, question: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        answer = input(f"{question}{suffix}: ").strip()
        return answer or default

    def ask_secret(self, question: str) -> str:
        return getpass.getpass(f"{question}: ")

    def ask_choice(self, question: str, choices: list[str], default: int = 0) -> int:
        self.say(question)
        for idx, choice in enumerate(choices, start=1):
            marker = ">" if idx - 1 == default else " "
            self.say(f"  {marker} [{idx}] {choice}")
        while True:
            raw = input(f"Choice [{default + 1}]: ").strip()
            if not raw:
                return default
            try:
                parsed = int(raw) - 1
            except ValueError:
                self.say(f"  Please enter a number 1-{len(choices)}.")
                continue
            if 0 <= parsed < len(choices):
                return parsed
            self.say(f"  Please enter a number 1-{len(choices)}.")

    def confirm(self, question: str, default: bool = False) -> bool:
        suffix = "[Y/n]" if default else "[y/N]"
        raw = input(f"{question} {suffix} ").strip().lower()
        if not raw:
            return default
        return raw in ("y", "yes", "true", "1")


class ScriptedPrompter:
    """Fake prompter used by tests. Returns answers from a fixed script.

    Each `ask*`/`confirm` call pulls the next value from the script. The
    script entries can be any of the types the wizard expects:
    - `ask` / `ask_secret` → str
    - `ask_choice` → int (zero-based index)
    - `confirm` → bool
    """

    def __init__(self, script: list[object]) -> None:
        self._script: Iterator[object] = iter(script)
        self.output: list[str] = []

    def say(self, message: str) -> None:
        self.output.append(message)

    def ask(self, question: str, default: str = "") -> str:
        value = next(self._script)
        if isinstance(value, str):
            return value or default
        raise TypeError(f"ScriptedPrompter.ask expected str, got {type(value).__name__}")

    def ask_secret(self, question: str) -> str:
        value = next(self._script)
        if isinstance(value, str):
            return value
        raise TypeError(f"ScriptedPrompter.ask_secret expected str, got {type(value).__name__}")

    def ask_choice(self, question: str, choices: list[str], default: int = 0) -> int:
        value = next(self._script)
        if isinstance(value, int):
            return value
        raise TypeError(f"ScriptedPrompter.ask_choice expected int, got {type(value).__name__}")

    def confirm(self, question: str, default: bool = False) -> bool:
        value = next(self._script)
        if isinstance(value, bool):
            return value
        raise TypeError(f"ScriptedPrompter.confirm expected bool, got {type(value).__name__}")
