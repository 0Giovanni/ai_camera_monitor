"""Replay four timestamp-sampled MP4 frames through the existing alert pipeline.

Run from the checkout: python -m scripts.replay_video --help
No RTSP readers or webhook server are started. Notifications require --notify.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path


def extract_frames(
    video: Path, output: Path, start: float, interval: float
) -> list[str]:
    """Decode sequentially by media timestamps; retain four lossless PNG frames."""
    import av

    if not math.isfinite(start) or start < 0:
        raise ValueError("start must be finite and nonnegative")
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("interval must be finite and positive")
    output.mkdir(parents=True, exist_ok=False)
    paths: list[str] = []
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        origin = None
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            if origin is None:
                origin = frame.time
            if frame.time - origin + 1e-6 < start + len(paths) * interval:
                continue
            path = output / f"frame_{len(paths) + 1:03d}.png"
            frame.to_image().save(path, format="PNG")
            paths.append(str(path))
            if len(paths) == 4:
                return paths
    raise ValueError(
        f"Video has insufficient timestamped frames: sampled {len(paths)}/4"
    )


def run_pipeline(frames: list[str], camera: str, alert_id: str, notify: bool) -> dict:
    # Import only after main has loaded configuration.
    from listener import daemon

    alert = {
        "id": alert_id,
        "camera_id": camera,
        "camera_label": camera,
        "classification": "motion",
        "timestamp": datetime.now(UTC).isoformat(),
        "frames": frames,
    }
    result = daemon._run_pipeline(alert)
    if notify and result.get("status") != "dropped":
        import time

        from infra import pipeline_cooldown

        pipeline_cooldown.record_hit(
            camera, result.get("classification", "unknown"), time.monotonic()
        )
        chat = os.environ["TELEGRAM_HOME_CHAT_ID"]
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        for slot, sender in (
            ("tg1", daemon._send_tg1),
            ("tg2", daemon._send_tg2),
            ("tg3", daemon._send_tg3),
        ):
            sender(result.get(slot), alert_id, chat, token, camera)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--camera",
        required=True,
        help="Camera ID used for existing gate/ROI thresholds",
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, default=Path("data/debug/replay"))
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Decode without models, VLM or notifications",
    )
    parser.add_argument(
        "--notify", action="store_true", help="Explicitly enable real Telegram sends"
    )
    args = parser.parse_args(argv)
    from dotenv import load_dotenv

    load_dotenv(args.env_file)
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("FARMSURV_PROJECT_ROOT", str(root))
    # Do not start background camera, API or watchdog services.
    event_id = str(uuid.uuid4())
    output = args.output.resolve() / event_id
    try:
        frames = extract_frames(args.video, output, args.start, args.interval)
        result = {"id": event_id, "frames": frames, "mode": "extract-only"}
        if not args.extract_only:
            result = run_pipeline(frames, args.camera, event_id, args.notify)
        (output / "result.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "id": event_id,
                    "output": str(output),
                    "status": result.get("status", "extracted"),
                }
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001 -- CLI reports failure with nonzero status
        parser.exit(1, f"Replay failed: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
