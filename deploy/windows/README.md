# Windows 11 proof-of-concept deployment

Native Windows execution is an implementation target, not yet a verified platform.
Start with a fresh Windows 11 x64 checkout. Git and uv must be installed and
available in PowerShell. Obtain uv from its official installation guide:
https://docs.astral.sh/uv/getting-started/installation/ .
Python 3.11 can be installed by uv. No administrator privileges or service
installation are needed for extraction-only evaluation.

## Controlled local checklist — installation and extraction only

1. Confirm Git/uv are available. Clone the feature branch into a new directory
   (do not overwrite an existing checkout). Run these commands in PowerShell:

```powershell
git --version
uv --version
git clone --branch feature/windows11-video-poc https://github.com/0Giovanni/ai_camera_monitor.git ai_camera_monitor-poc
Set-Location .\ai_camera_monitor-poc
git branch --show-current
git rev-parse HEAD
uv python install 3.11
uv sync --frozen --extra dev --extra windows --extra recognition --python 3.11
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; stop here.' }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$env:FARMSURV_PROJECT_ROOT = (Get-Location).Path
$env:FARMSURV_DATA_DIR = Join-Path (Get-Location) 'data'
$env:FARMSURV_LOGS_DIR = Join-Path (Get-Location) 'logs'
$env:FARMSURV_API_ENABLED = '0'
$env:FARMSURV_MCP_ENABLED = '0'
$env:PERSON_EMBEDDER_LIVE = '0'
$env:ANIMAL_EMBEDDER_LIVE = '0'
.\.venv\Scripts\python.exe -c "import struct, av; from zoneinfo import ZoneInfo; print('Python bits:', struct.calcsize('P')*8); print('PyAV:', av.__version__); print(ZoneInfo('America/New_York'))"
if ($LASTEXITCODE -ne 0) { throw 'Runtime import failed; stop here.' }
```

2. Choose a readable, authorized MP4 at least three seconds long. Replace the
   example path below. No camera configuration is needed for extraction-only;
   REPLAY is merely the required CLI label.

```powershell
$videoPath = 'C:\Videos\sample.mp4'
if (-not (Test-Path -LiteralPath $videoPath -PathType Leaf)) { throw 'Set videoPath to an existing MP4.' }
.\.venv\Scripts\python.exe -m scripts.replay_video --help
.\.venv\Scripts\python.exe -m scripts.replay_video "$videoPath" --camera REPLAY --extract-only --env-file .\.env --output .\data\debug\replay --start 0 --interval 0.5
if ($LASTEXITCODE -ne 0) { throw 'Extraction failed; inspect the error before continuing.' }
$run = Get-ChildItem .\data\debug\replay -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$frames = @(Get-ChildItem $run.FullName -Filter 'frame_*.png')
if ($frames.Count -ne 4) { throw 'Expected four extracted PNG frames.' }
Get-Content (Join-Path $run.FullName 'result.json')
```

3. Confirm four full-resolution PNGs, mode extract-only, and a successful exit.
   No model is loaded and no camera, VLM, Telegram or service is contacted in
   this mode. Short/corrupt/video-less files should fail nonzero; preserve the
   diagnostic and partial output for review. Record Windows version, commit,
   Python/PyAV versions, media codec/resolution and the output summary, without
   sharing private footage.
4. Use the standalone CLI above as the primary initial acceptance test.
   Full pytest collection imports inference modules and is a later step.
   The Linux review test counts are not Windows acceptance results.

### Things that can stop this first test

- Git/uv absent from PATH, blocked package/interpreter downloads, certificate or
  proxy failures, unsupported 32-bit/ARM environment, insufficient disk/RAM.
  Installation includes the project's large Torch stack even for extraction;
  do not assume CUDA packages imply usable GPU acceleration.
- Native wheel/DLL loading failures. Use Windows x64 Python 3.11 and the locked
  versions; investigate the exact error and install Microsoft's supported
  Visual C++ runtime if required. Do not disable TLS/hash validation.
- Wrong working directory: scripts.replay_video is run from the source checkout,
  not as a standalone installed CLI. Missing scripts or a different branch will
  prevent module discovery.
- Input path/permissions, an unsupported MP4 codec, no video stream/timestamps,
  insufficient duration, or a non-writable output directory.
- Existing .env/credential files must be preserved. Extraction-only does not
  validate their values; placeholders/blank coordinates block later inference.
  External SCM services, Tailscale and reolink-cli are NOT prerequisites here.
- Sparse cleanup fixtures are verified on Linux only. Do not run the entire
  cleanup suite on NTFS until disk allocation behavior has been checked.

Do not start listener.daemon, omit --extract-only, enable live recognition flags,
or pass --notify until this first checkpoint is reviewed.

The recognition extra supplies transformers for live person CLIP; omit it if unused.
The windows extra supplies Waitress, used instead of Flask's development server on
Windows. YOLO remains on CPU on Windows. No CUDA/DirectML provider changes are made.

Edit local configuration before starting inference: set the farm coordinates and
required tunables, configure the model/vision endpoint and real per-app credential
files only for the workflows needed. Set API/MCP bind addresses explicitly and
use strong tokens if enabled. Do not use the example credential placeholders.
Apply Windows ACLs for the service account; chmod instructions do not secure NTFS.

## Camera-free MP4 evaluation

```powershell
.venv\Scripts\python.exe -m scripts.replay_video clip.mp4 --camera FRONT --extract-only
.venv\Scripts\python.exe -m scripts.replay_video clip.mp4 --camera FRONT --start 2 --interval 0.5
```

Run from the checkout. Use a configured camera ID for the intended ROI/motion
thresholds even though no camera is contacted. A run samples one four-frame event
at media offsets start, start+interval, start+2*interval, start+3*interval.
This is a sampled-event evaluator, not a continuous full-video motion detector.
EOF before four samples is an error. Output is unique per run under
data/debug/replay (override --output). PNGs and result.json persist for inspection.

Without --extract-only the existing gate, YOLO, VLM, detail and recognition stages
run unchanged; they require their normal configuration/models/endpoints. No RTSP,
webhook/API servers or background supervisors are started. Recognition flags still
control real versus synthetic embedding behavior; extraction proves no recognition
accuracy. Event timestamp is evaluation wall time, so night rules use that time.
Use test configuration and isolated FARMSURV_DATA_DIR/FARMSURV_LOGS_DIR to keep
evaluation artifacts separate from live state. Read-only thresholds still come
from the project configuration.

Telegram is off by default. Add --notify only when real delivery is intended and
per-app credentials are configured. It uses existing sender helpers and cooldown
recording. Never use --notify for automated tests with production configuration.
The command prints an output path and exits nonzero on decoding/pipeline errors.

## Live operation and service supervision

Foreground: .venv\Scripts\python.exe -m listener.daemon. This retains RTSP capture,
detection, VLM, matching and Telegram behavior and uses Waitress on Windows.
Configure Windows Firewall for the chosen listener/API/MCP interfaces. The camera
management reolink-cli executable must be separately available for management
features; native Windows support of that external tool is unverified.

An ordinary python.exe command is NOT an SCM service binary. For background
operation, install a reviewed Windows service wrapper such as WinSW separately;
configure its executable as the absolute .venv\Scripts\python.exe path,
arguments '-m listener.daemon', working directory as the checkout, and environment
as above. Use one supervisor with restart recovery, log rotation and a restricted
account. No wrapper binary is downloaded or service installed automatically.

Set FARMSURV_WINDOWS_SERVICE to that installed wrapper's exact service name.
The API's listener PID lookup and scripts.watchdog_restart then use
sc.exe queryex/stop/start. Failure/permission errors are reported; absent service
configuration returns no PID. The internal macOS Bash watchdog is disabled on
Windows; configure SCM/wrapper recovery rather than two restart loops.
sc.exe parsing must be validated on the target Windows language/locale.

macOS continues to use its existing launchd/plist, lsof, watchdog and Flask host.
Historical plist_keepalive health fields refer only to launchd; false on Windows
does not imply missing Windows recovery policy.

## Required local acceptance

- Fresh install; timezone database; paths containing spaces/Unicode; NTFS permissions.
- Replay known MP4s, short/corrupt videos and expected gate decisions.
- Real YOLO model checksum/loading; VLM endpoint and optional live embeddings.
- Live camera RTSP startup, reconnect, stop and stream geometry; notifications.
- Service install/start/stop/reboot/recovery, correct PID, firewall and tailnet binding.
- CPU load/latency/memory under multiple cameras; GPU acceleration is future work.

Cloud results exercise Linux execution and mocked Windows command contracts only.
