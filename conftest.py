"""Repository-root conftest.

Insulates the test suite from ambient pytest plugins (e.g., ROS' launch_testing
entrypoint) that may be installed system-wide on developer machines.

Note on ambient ROS plugins
---------------------------
On hosts with /opt/ros/<distro> on the default Python path, pytest will
autoload `launch_testing` and `launch_ros` entry-point plugins. If the
host's `lark` package is missing (a common case), plugin loading fails
before conftest gets a chance to run. The most reliable mitigation is one
of:

  1. Run pytest with `-p no:launch_testing -p no:launch_ros` (recommended).
  2. `unset PYTHONPATH` / `env -u PYTHONPATH` before invoking pytest.
  3. Install a minimal `lark` stub into the active interpreter.

This conftest takes care of (3) defensively for any in-process code that
runs after rootdir-conftest loading (i.e., the tests themselves), and
removes a PYTHONPATH that leaks ROS site-packages into subprocess
invocations of `agentos` made from tests.
"""
from __future__ import annotations

import os
import sys
import types

# Pin plugin list to empty for THIS conftest scope. Subdir conftests can opt
# back in if they ever need to.
collect_ignore_glob: list[str] = []
pytest_plugins: list[str] = []


def _install_lark_stub() -> None:
    """Install a minimal `lark` stub if real lark is unavailable.

    This prevents downstream code (and any late-loaded launch_testing internals)
    from crashing on `from lark import Lark/Token`. Does NOT help with pytest's
    own plugin autoload (which runs BEFORE rootdir conftest); for that, prefer
    `-p no:launch_testing -p no:launch_ros` on the command line.
    """
    try:
        import lark  # noqa: F401
        return
    except ImportError:
        pass

    m = types.ModuleType("lark")
    for name in ("Lark", "Token", "Transformer", "Tree", "Visitor", "v_args"):
        setattr(m, name, type(name, (), {}))
    exc = types.ModuleType("lark.exceptions")

    class _LarkErr(Exception):
        pass

    exc.UnexpectedCharacters = type("UnexpectedCharacters", (_LarkErr,), {})
    exc.UnexpectedToken = type("UnexpectedToken", (_LarkErr,), {})
    exc.LarkError = _LarkErr
    m.exceptions = exc
    sys.modules["lark"] = m
    sys.modules["lark.exceptions"] = exc


_install_lark_stub()

# Make sure PYTHONPATH doesn't leak ambient stuff into subprocess invocations
# of `agentos`/`pytest` from tests.
if "PYTHONPATH" in os.environ and "/opt/ros/" in os.environ.get("PYTHONPATH", ""):
    os.environ.pop("PYTHONPATH", None)
