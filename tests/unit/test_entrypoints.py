"""Import-smoke for `__main__.py` so the entrypoint line is covered.

We don't invoke `main()` because that would try to load config.yaml
and start the adapters. The `from datronis_relay.main import main`
line at the top of `__main__.py` is the only thing we need to cover.
"""

from __future__ import annotations

import datronis_relay
import datronis_relay.__main__ as dunder_main


class TestEntrypoint:
    def test_dunder_main_reexports_callable_main(self) -> None:
        assert callable(dunder_main.main)

    def test_package_root_has_string_version(self) -> None:
        assert isinstance(datronis_relay.__version__, str)
        assert datronis_relay.__version__ == "1.0.0"
