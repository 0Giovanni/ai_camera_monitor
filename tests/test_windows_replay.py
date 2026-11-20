"""Platform contract tests plus actual MP4 decoding in an unstubbed subprocess."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from infra import platform_service
from scripts import replay_video


def test_service_running_pid_and_restart(monkeypatch):
    monkeypatch.setenv("FARMSURV_WINDOWS_SERVICE", "Camera Monitor")
    responses = iter(
        [
            "STATE : 4 RUNNING\n PID : 123",
            "STATE : 4 RUNNING\n PID : 123",
            "",
            "STATE : 1 STOPPED\n PID : 0",
            "",
            "STATE : 4 RUNNING\n PID : 456",
        ]
    )
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, next(responses), "")

    monkeypatch.setattr(platform_service.subprocess, "run", run)
    assert platform_service.windows_service_pid() == 123
    assert platform_service.restart_windows_service() == (
        0,
        "Service running after restart",
    )
    assert ["sc.exe", "stop", "Camera Monitor"] in calls
    assert ["sc.exe", "start", "Camera Monitor"] in calls


def test_service_missing_configuration(monkeypatch):
    monkeypatch.delenv("FARMSURV_WINDOWS_SERVICE", raising=False)
    assert platform_service.windows_service_pid() is None
    assert platform_service.restart_windows_service()[0] == 1


def test_service_query_failure(monkeypatch):
    monkeypatch.setenv("FARMSURV_WINDOWS_SERVICE", "test")
    monkeypatch.setattr(
        platform_service.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 5, "", ""),
    )
    assert platform_service.windows_service_pid() is None
    assert platform_service.restart_windows_service()[0] == 1


def test_windows_tailnet_command(monkeypatch):
    from infra import net_bind

    monkeypatch.delenv("TAILNET_BIND_ADDR", raising=False)
    monkeypatch.setattr(net_bind.platform, "system", lambda: "Windows")
    command = Mock(return_value="100.64.0.2\n")
    monkeypatch.setattr(net_bind.subprocess, "check_output", command)
    assert net_bind._resolve_tailnet_ip() == "100.64.0.2"
    assert command.call_args.args[0] == ["tailscale", "ip", "-4"]


def test_replay_uses_pipeline_without_notifications(monkeypatch):
    from listener import daemon

    pipeline = Mock(return_value={"status": "ok", "classification": "person"})
    sender = Mock()
    monkeypatch.setattr(daemon, "_run_pipeline", pipeline)
    monkeypatch.setattr(daemon, "_send_tg1", sender)
    assert (
        replay_video.run_pipeline(["a", "b", "c", "d"], "REPLAY", "evt", False)[
            "status"
        ]
        == "ok"
    )
    assert pipeline.call_args.args[0]["frames"] == ["a", "b", "c", "d"]
    sender.assert_not_called()


def test_real_mp4_decode_and_short_video_failure(tmp_path):
    # conftest deliberately stubs av. This child uses the real installed PyAV.
    code = r"""
import av
import numpy as np
from pathlib import Path
import sys
from scripts.replay_video import main
root = Path(sys.argv[1])
video = root / 'input.mp4'
with av.open(str(video), 'w') as out:
    stream = out.add_stream('mpeg4', rate=10)
    stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
    for i in range(20):
        rgb = np.zeros((48, 64, 3), dtype=np.uint8)
        rgb[:, :, 0] = i * 10
        frame = av.VideoFrame.from_ndarray(rgb, format='rgb24')
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode():
        out.mux(packet)
assert main([str(video), '--camera', 'REPLAY', '--extract-only',
             '--output', str(root / 'frames')]) == 0
from scripts.replay_video import extract_frames
try:
    extract_frames(video, root / 'short', 10, .5)
except ValueError:
    pass
else:
    raise AssertionError('Expected short-video error')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    result_file = next((tmp_path / "frames").glob("*/result.json"))
    data = json.loads(result_file.read_text())
    assert len(data["frames"]) == 4
    from PIL import Image

    levels = []
    for path in data["frames"]:
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == (64, 48)
            levels.append(np_mean_red(image))
    assert levels == sorted(levels) and levels[-1] > levels[0]


def np_mean_red(image):
    return image.getpixel((0, 0))[0]


@pytest.mark.parametrize("start,interval", [(-1, 0.5), (0, 0), (float("nan"), 0.5)])
def test_invalid_sample_window(tmp_path, start, interval):
    with pytest.raises(ValueError):
        replay_video.extract_frames(
            Path("unused.mp4"), tmp_path / "out", start, interval
        )


def test_windows_socket_health(monkeypatch):
    import socket

    from listener import health
    from listener.health import HealthReporter

    monkeypatch.setattr(health.platform, "system", lambda: "Windows")
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        assert HealthReporter._is_port_bound(port)
    assert not HealthReporter._is_port_bound(port)


def test_windows_watchdog_does_not_launch_bash(monkeypatch):
    from listener import health

    monkeypatch.setattr(health.platform, "system", lambda: "Windows")
    run = Mock()
    monkeypatch.setattr(health.subprocess, "run", run)
    health._WatchdogLoop._fire(object())
    run.assert_not_called()


def test_service_stop_failure_is_reported(monkeypatch):
    monkeypatch.setenv("FARMSURV_WINDOWS_SERVICE", "test")
    responses = iter(
        [
            subprocess.CompletedProcess([], 0, "STATE : 4 RUNNING\n PID : 123", ""),
            subprocess.CompletedProcess([], 5, "", ""),
        ]
    )
    monkeypatch.setattr(
        platform_service.subprocess, "run", lambda *a, **k: next(responses)
    )
    code, message = platform_service.restart_windows_service()
    assert code == 1 and "stop failed" in message


def test_notify_requires_explicit_opt_in(monkeypatch):
    from listener import daemon

    monkeypatch.setenv("TELEGRAM_HOME_CHAT_ID", "test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-not-a-credential")
    monkeypatch.setattr(
        daemon,
        "_run_pipeline",
        Mock(return_value={"status": "ok", "classification": "person"}),
    )
    senders = [Mock(), Mock(), Mock()]
    for slot, sender in zip(("tg1", "tg2", "tg3"), senders):
        monkeypatch.setattr(daemon, "_send_" + slot, sender)
    replay_video.run_pipeline(["a"] * 4, "REPLAY", "evt", True)
    assert all(sender.call_count == 1 for sender in senders)


def test_service_start_timeout(monkeypatch):
    monkeypatch.setenv("FARMSURV_WINDOWS_SERVICE", "test")
    query = Mock(side_effect=[(1, 0), (1, 0), (2, 0)])
    monkeypatch.setattr(platform_service, "_query", query)
    monkeypatch.setattr(
        platform_service.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""),
    )
    assert platform_service.restart_windows_service(timeout=0) == (
        1,
        "Timed out waiting for service start",
    )


def test_windows_path_defaults_in_isolated_process():
    code = """
import platform
from dotenv import load_dotenv
load_dotenv()
# Load native libraries on the real host before simulating path policy.
from infra import paths
import importlib
platform.system = lambda: 'Windows'
import os
os.environ.pop('FARMSURV_PROJECT_ROOT', None)
os.environ.pop('BROWSER_CHROME_PATH', None)
from pathlib import Path
importlib.reload(paths)
assert paths.PROJECT_ROOT == str(Path(paths.__file__).resolve().parents[1])
assert Path(paths.BROWSER_CHROME_PATH).parts[-4:] == ('Google', 'Chrome', 'Application', 'chrome.exe')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_windows_health_uses_configured_interface(monkeypatch):
    from listener import health

    monkeypatch.setattr(health.platform, "system", lambda: "Windows")
    monkeypatch.setenv("FARMSURV_API_PORT", "18092")
    monkeypatch.setenv("FARMSURV_API_BIND", "tailnet-only")
    connection = Mock()
    from unittest.mock import MagicMock

    connection.return_value = MagicMock()
    monkeypatch.setattr(health.socket, "create_connection", connection)
    assert health.HealthReporter._is_port_bound(18092)
    from infra.net_bind import TAILNET_BIND

    assert connection.call_args.args[0] == (TAILNET_BIND, 18092)
