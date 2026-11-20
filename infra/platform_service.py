"""Windows service control for a separately installed service wrapper.

No service is installed implicitly. Set FARMSURV_WINDOWS_SERVICE to the wrapper's
service name. SCM operations require suitable local permissions.
"""

from __future__ import annotations

import os
import re
import subprocess
import time


def _service_name() -> str:
    name = os.environ.get("FARMSURV_WINDOWS_SERVICE", "").strip()
    if not name:
        raise ValueError("Set FARMSURV_WINDOWS_SERVICE to an installed service name")
    return name


def _query(name: str) -> tuple[int, int]:
    result = subprocess.run(
        ["sc.exe", "queryex", name],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Service query failed (exit {result.returncode})")
    state = re.search(r"STATE\s*:\s*(\d+)", result.stdout)
    pid = re.search(r"PID\s*:\s*(\d+)", result.stdout)
    if not state or not pid:
        raise RuntimeError("Unrecognized sc.exe queryex output")
    return int(state[1]), int(pid[1])


def windows_service_pid() -> int | None:
    """Return a running service PID, or None when unavailable."""
    try:
        state, pid = _query(_service_name())
        return pid if state == 4 and pid > 0 else None
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
        return None


def restart_windows_service(timeout: float = 60) -> tuple[int, str]:
    """Stop, await STOPPED, start, await RUNNING; never install a service."""
    try:
        name = _service_name()
        state, _ = _query(name)
        if state != 1:
            result = subprocess.run(
                ["sc.exe", "stop", name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode:
                return 1, f"Service stop failed (exit {result.returncode})"
        deadline = time.monotonic() + timeout
        while _query(name)[0] != 1:
            if time.monotonic() >= deadline:
                return 1, "Timed out waiting for service stop"
            time.sleep(0.25)
        result = subprocess.run(
            ["sc.exe", "start", name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode:
            return 1, f"Service start failed (exit {result.returncode})"
        deadline = time.monotonic() + timeout
        while True:
            state, pid = _query(name)
            if state == 4 and pid > 0:
                return 0, "Service running after restart"
            if time.monotonic() >= deadline:
                return 1, "Timed out waiting for service start"
            time.sleep(0.25)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"Service restart unavailable: {exc}"
