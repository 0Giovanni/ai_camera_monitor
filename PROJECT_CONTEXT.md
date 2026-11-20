# Project context and architectural assessment

Assessment date: 2026-11-20. Baseline commit: `c60c34f14705e555f05121a931963dfd4425f42b`.

## Implementation update — 2026-11-20

The original assessment below is a historical baseline. Branch `feature/windows11-video-poc` contains the reviewed incremental implementation. See the latest PROGRESS.md entry for commit/push status; main must remain unmerged.

Implemented:
- Windows SCM query/restart adapter for an explicitly configured, separately installed wrapper service. Windows listener PID reporting delegates to it; macOS launchctl restart/PID behavior remains.
- Windows project/Chrome defaults, Tailscale CLI discovery (explicit bind override remains preferred), tzdata, atomic event replacement, and plistlib-based launchd configuration reading.
- Windows socket health checks, disabling the internal launchd Bash watchdog on Windows, and Waitress hosting via the windows extra. macOS hosting/watchdog paths remain.
- MP4 sampled-event evaluator in `scripts/replay_video.py`: real timestamp-based decoding to four PNGs, extraction-only option, existing pipeline invocation, unique output directories, and explicit notification opt-in.
- Manifest/lock declarations for OpenCV/tzdata, optional transformers and Waitress, and package discovery for both missing matcher packages. Optional recognition pins transformers below 5; lock resolution adjusts its Hugging Face dependencies.
- Test fixtures for disk cleanup now create sparse files with the same logical sizes; assertions and cleanup production code are unchanged.
- Operator guide: `deploy/windows/README.md`.

Still unverified: native Windows execution, actual SCM wrapper installation/recovery, locale-specific sc.exe output, Windows RTSP/codecs, GPU inference, real YOLO/VLM/re-ID accuracy/performance, live Telegram, and target-machine sustained load. No CUDA/provider, model algorithm, recognition threshold, VLM prompt, camera recipe or notification formatting changes were made. Replay evaluates one sampled event, not continuous automatic event detection over an entire video. It uses evaluation wall time for night rules. Configuration/endpoints/models are required for full-pipeline mode; extract-only avoids them.

## Goal and status

Evaluate the camera-monitoring application as a proof of concept for eventual Windows deployment. Preserve working behavior while establishing platform portability and measurable capacity. The initial assessment changed documentation only; the implementation update above supersedes those baseline observations. Windows, real camera ingest, live models, and production throughput have not been validated. Windows 11 is the target; GPU model/VRAM, camera count/resolution/FPS, event rate, and latency targets remain open.

## Architecture and data flow

The application is a modular Python monolith with background threads, local filesystem state, and external network services. It is not a durable job-processing system.

1. `listener/daemon.py` loads layered dotenv configuration, creates the Flask app, starts camera readers, cleanup, optional MCP/API threads, and health/watchdog reporting. The executable uses Waitress on Windows and Flask `app.run` elsewhere.
2. `infra/camera_creds.py` resolves camera configuration and validates source IPs. `/alert` normalizes Reolink webhook payloads and maps camera names. It trusts `X-Forwarded-For` when supplied; a deployment must define trusted proxy boundaries.
3. `infra/frame_capture.py` maintains a persistent PyAV RTSP reader per camera, with a lock-protected deque of PIL images and reconnect supervision. All decoded frames are converted to images; no explicit GPU decoding is configured. OpenCV also probes stream geometry. Event capture starts a thread/Future, selects ring slots [-5,-4,-2,-1], waits 0.5 seconds for the final grab, and writes four PNGs. Historical stride descriptions should not replace this actual selection behavior.
4. `listener/pipeline.py` provides stages orchestrated by `_run_pipeline` in the daemon. `infra/gate.py`, `frame_diff.py`, `quick_classifier.py`, masking/ROI and night modules perform motion filtering, YOLO classification, crop selection, and suppression. YOLO uses a lazy singleton and canonical 640x640 letterboxing; preserve original evidence separately from inference transforms.
5. `infra/vision_analyzer.py` sends crops as base64 images to an OpenAI-compatible vision endpoint. VM1 verifies classification and controls routing; unsure results drop. Cooldown is checked after VM1, so it does not avoid capture/gate/VM1 cost. VM2 supplies class-specific detail. Endpoint settings are external configuration, not a bundled LLM server.
6. `animal_matcher`, `person_matcher`, and `vehicle_matcher` combine descriptors/candidates and cosine/attribute matching. Animal live embeddings use MegaDescriptor-S-224 through timm; person live embeddings use CLIP-ViT-B/32 through transformers. Disabled live modes generate synthetic embeddings, which are test scaffolding, not recognition evidence.
7. `telegram_formatter` builds alert/detail/match messages; dispatcher sends up to three stages with media conversion and synchronous HTTP. In actual `/alert` code, the pipeline completes before these sends. Despite the route docstring promising 202, the normal path returns 200 after processing; failure paths can also return 200 to avoid retry storms. Missing readers/capture failures return 503.
8. `infra/event_record.py` writes per-event JSON via a temporary file, fsync, close, and atomic os.replace. Other records include JSON/JSONL, PNG artifacts, identity JSON/NPZ and enrollment data. There is no central database or durable work queue. Cleanup and upload sweeps enforce retention.
9. `infra/api_server.py` and `infra/mcp_server.py` expose resource/tool interfaces on configurable ports (defaults 8092/8091), using threaded standard-library HTTP servers and bearer tokens; listener defaults to 8090. API resource implementations live in `infra/farm_api`. Health, daily reports, shell smoke scripts and launchd provide operations support.

Primary references: `README.md`, `docs/ARCHITECTURE-alert-pipeline-2026-09-27.md`, `docs/API.md`, `docs/MCP-API.md`, `docs/cleanup-policy.md`. Historical/operator-specific claims must be checked against current code.

## Dependency assessment

| Layer | Declared components | Deployment implications |
| --- | --- | --- |
| Runtime/configuration | Python >=3.11, python-dotenv, suntime | Documented interpreter is 3.11; validate timezone data on Windows for `ZoneInfo("America/New_York")` and provide tzdata if absent. dotenv precedence and service-account home directory affect behavior. |
| Ingress | Flask | Waitress is selected on Windows via the windows extra; macOS retains the development server. Multiple processes would duplicate readers and in-memory state without redesign. |
| Video/images | av, Pillow, NumPy | Requires compatible native wheels/codecs; PyAV bundles/native FFmpeg support must be checked on Windows. Hardware decoding is a separate decision from inference. |
| Detection | onnxruntime | Standard package and explicit CoreML/CPU selection do not enable NVIDIA CUDA. Model is downloaded separately with pinned hash verification. |
| Embeddings | torch, timm | Large native/transitive footprint including torchvision/Hugging Face tooling. Models are external downloads. CPU execution is current default. |
| Messaging/network | httpx, python-telegram-bot | Telegram outbound HTTPS, camera LAN RTSP and management access, optional vision endpoint, API/MCP clients are distinct connectivity requirements. |
| Development | pytest, pytest-asyncio, ruff, pyright, PyYAML | Test fixtures deliberately mock some runtime behavior. Makefile and shell helpers need portable equivalents. |

`uv.lock` pins the resolved dependency graph; lower bounds in `pyproject.toml` alone are not a reproducible platform deployment specification. Linux onboarding installed 67 locked dependencies, including CUDA 13-related PyTorch packages, but CUDA was unavailable. Those packages do not establish a Windows-compatible accelerator stack.

Initial declaration gaps (resolved by this branch): OpenCV is used in frame capture/tests but previously absent from the manifest/lock; now declared. The live person loader imports `transformers`, now declared in the optional recognition extra. Package discovery originally omitted person_matcher and animal_matcher, now included: checkout execution can mask a distributable-wheel problem. Validate an installed wheel outside the checkout before distribution.

External prerequisites: compatible Reolink cameras/firmware and reachable RTSP; `reolink-cli` executable for management/recipe operations (`infra/reolink.py`, `scripts/register_cameras.py`), whose Windows availability is unverified; YOLO artifact; Hugging Face model downloads/cache for live re-ID; optional vision model server; Telegram credentials and destination; farm coordinates. Model/download destinations include GitHub release assets and Hugging Face infrastructure; determine actual redirects before proposing network rules. No secrets are recorded here. Review upstream code/model licensing before distribution; repository LICENSE alone does not cover third-party model rights.

## macOS assumptions and Windows compatibility

| Component/evidence | Issue | Recommended direction (not implemented) |
| --- | --- | --- |
| daemon `generate_plist`, deploy/bin plists | launchd, LaunchAgents, Unix interpreter paths | Windows service wrapper/Service Control Manager integration, explicit account, working directory and restart policy. |
| `scripts/watchdog_restart.py`, `bin/health_watchdog.sh` | launchctl, GUI uid domain, `os.getuid`, Bash | One platform supervisor adapter; avoid competing watchdog restart loops. |
| `listener/health.py`, `infra/farm_api/listener.py` | plutil/lsof/launchctl health and PID discovery | Portable process/socket health and Windows service-state integration. Missing commands can report false unhealthy status. |
| `infra/net_bind.py` | ifconfig-based tailnet discovery, fallback CGNAT address | Explicit configured bind address first; test Windows Tailscale routing/firewall. Never assume the sample fallback exists. |
| `infra/quick_classifier.py` | CoreML-specific provider preference and shape workarounds | Configurable backend with validated CPU baseline and explicit CUDA/DirectML support. Keep checksum and transform parity. |
| `infra/paths.py` | macOS Chrome default, Unix-oriented defaults | Explicit configurable project/data/log/browser locations; writable Windows service directories. Check actual browser consumers before installing browser tools. |
| filesystem / scripts | `.venv/bin`, Bash/Make, chmod semantics, rename-over-existing behavior | PowerShell/Python operational commands; Windows ACLs, path quoting/Unicode, file locks, atomic replace and shutdown tests. `event_record.py` uses os.rename, whose overwrite semantics differ on Windows; this branch changes it to os.replace. |
| timezone | hardcoded America/New_York in paths plus display config | Ensure zoneinfo database exists; decide deployment timezone deliberately rather than inheriting operator settings. |

Most business logic uses portable Python/NumPy/Pillow APIs, so a Windows port looks feasible, but feasibility is not demonstrated deployment support. Native Windows is the proposed target baseline; WSL2 is an optional development route, not proof of native service compatibility.

## GPU inference requirements

- YOLO currently selects only CoreMLExecutionProvider and CPUExecutionProvider (`quick_classifier.py`); Windows runs CPU even if a CUDA provider is installed. Actual startup must report requested and active providers, model path/hash, and fallback behavior.
- NVIDIA acceleration requires a compatible NVIDIA driver, GPU-capable ONNX Runtime distribution, and its documented CUDA/cuDNN matrix. Do not co-install competing ONNX Runtime distributions. PyTorch and ORT compatibility must be validated separately.
- AMD/Intel evaluation could consider ONNX Runtime DirectML, but neither provider selection nor operator/model compatibility is established here. Do not promise equivalent speed or accuracy without measurements.
- Both live embedding loaders construct CPU models/tensors without explicit `.to(device)` placement. A CUDA PyTorch wheel alone is insufficient. Future work needs device selection, consistent tensor placement, warmup, bounded concurrency and CPU fallback policy. Recalibrate recognition thresholds if precision/backend changes alter outputs.
- Vision LLM execution is external; it can share the Windows GPU or run elsewhere. Its model size, quantization, image tokens, context, request concurrency and backend will dominate VRAM requirements. No defensible VRAM minimum or FPS claim can be made from source alone. Inventory hardware, benchmark each model, then size combined peak memory with headroom.
- Capture/decode, PNG compression, motion analysis, transport and disk I/O remain CPU/network/storage work unless separately changed. GPU inference will not remove them.

## Processing bottlenecks and reliability risks

These are source-derived risks, not measured production regressions:

1. Synchronous webhook lifecycle includes capture wait, gate, VM1, VM2/matching, and Telegram; vision request timeouts are 30 and 60 seconds, dispatcher HTTP timeout is 10 seconds. Multiple sequential operations can cause long response tails. No bounded event queue/admission control was found in this route; burst traffic can accumulate request/capture threads.
2. Per-camera continuous full-frame decode and PIL conversion consume CPU and RAM regardless of alert rate. Ring memory roughly scales as cameras × slots × width × height × channels. At 12 RGB slots and 1920x1080 this is about 71 MiB per camera before object/copy overhead; use actual configured ring size and stream geometry for sizing. Source comments describing live 2 FPS are not an enforced FPS cap.
3. Four lossless PNG writes per event plus crops, visualization and Telegram conversion add compression, disk traffic, repeated reads and base64 expansion (~4/3 payload size). Preserve evidence policy while measuring avoidable copies and transform duplication.
4. `classify_batch` iterates frame-by-frame rather than issuing a tensor batch. Singleton lazy initialization, ONNX execution, shared cooldowns and learned mappings need concurrency review before increasing workers; read-only model use does not establish safe initialization or all shared-state operations.
5. VM1 and VM2 are serial external calls. Cooldown occurs after VM1, so repeated motion can still saturate the vision service. Multi-camera bursts can contend for the same model server/GPU.
6. Lazy model loading/network downloads add first-event latency and concurrent initialization risk. Synthetic embedding modes can conceal missing real recognition functionality.
7. Filesystem enumeration/history, per-event fsync, JSON/NPZ registry loads and retention scans scale with accumulated data; measure before adding databases or caches. NPZ/pickle-capable identity stores must be trusted local inputs.
8. RTSP demux holds a container lock across native iteration. Reconnect/shutdown paths need stalled-stream fault tests; a timeout joining a Python thread does not guarantee native work stopped. Geometry probing adds another camera connection.
9. Pipeline/Telegram errors may be acknowledged with 200 without durable retry; API process health is weaker evidence than working capture/inference/delivery. Establish separate readiness and end-to-end success metrics.

Measure event rate and burst size; capture age, capture/gate/VM1/VM2/match/send p50/p95/p99; CPU/RAM/VRAM/disk; RTSP lag/reconnect count; pending work, drops and failures. Add correlation IDs across stages. Use measured bottlenecks to choose optimization order.

## Staged implementation plan

| Stage | Scope | Exit evidence |
| --- | --- | --- |
| 0 — baseline and targets | Preserve this assessment; inventory Windows version, CPU/GPU/VRAM, cameras/FPS, event rates, latency/retention requirements; define a sanitized replay dataset. | Agreed acceptance thresholds and reproducible baseline; distinguish synthetic, replay and live results. |
| 1 — reproducible CPU package | Correct optional dependency/package discovery gaps, verify wheel installation outside source, define Windows lock/install procedure and local config validation. | Fresh Windows Python 3.11 install; imports and representative tests; invalid placeholders fail clearly. |
| 2 — Windows lifecycle | Abstract service supervision/health/network discovery; choose Windows WSGI hosting and service account; portable paths, ACLs, timezone and filesystem handling. | Start/stop/restart/reboot and stalled-camera recovery tests on native Windows; authenticated API/MCP requests and firewall validation. |
| 3 — real CPU vertical slice | Checksum-verified YOLO, recorded RTSP/replay, VM endpoint, real embedding optional features, sandbox Telegram delivery. | One complete event plus suppressions/errors; no synthetic recognition presented as live; recorded timings and accuracy. |
| 4 — GPU enablement | Explicit ORT/device configuration; NVIDIA first if target hardware supports it; model warmup and cache provisioning; consider DirectML separately. | Active provider/device proven, CPU/GPU numerical/decision parity, peak VRAM and latency measurements, documented fallback. |
| 5 — controlled throughput | Add bounded ingestion/work scheduling and idempotency/retry policy, isolate delivery; profile before batching/caching or altering preprocessing. | Agreed burst test without unbounded memory/thread growth; latency, loss/retry and retention thresholds met. Do not merely add WSGI workers that duplicate readers. |
| 6 — deployment hardening | Model/version/license inventory, secrets/ACLs, upgrade/rollback, structured diagnostics, recovery and long soak. | Repeatable clean-machine installation, reboot/network-loss/disk-pressure recovery, sustained multi-camera acceptance on target hardware. |

Proposals are intentionally separate from current behavior. No queue, Windows service, CUDA integration or production hosting change has been implemented by this assessment.
