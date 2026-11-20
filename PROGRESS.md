# Progress and handoff

## 2026-11-20 — architectural assessment and Windows planning

User scope: assess the proof of concept for eventual Windows deployment; identify architecture/dependencies, macOS ties, compatibility, GPU needs and bottlenecks; create continuity documents. No core modifications authorized for this task.

Baseline: `c60c34f14705e555f05121a931963dfd4425f42b`. Starting tracked/untracked status was clean. Created `AGENTS.md`, `PROJECT_CONTEXT.md`, and this file only.

Completed source inspection: manifest/lock and package discovery; daemon startup/webhook/pipeline; frame capture/reconnect; gate/YOLO providers; live/synthetic embedders; model transports; Telegram dispatch; API/MCP; filesystem paths/event persistence; health/watchdog and macOS deployment scripts. Context document records findings, evidence paths, uncertainties and a seven-stage proposal.

Main conclusions: current YOLO selects CoreML/CPU only; embedders do not explicitly select GPU devices; webhook handling is synchronous despite its 202 docstring; macOS supervision/health tooling is not Windows-compatible; OpenCV and transformers declaration gaps and matcher package discovery require follow-up. Windows support and hardware capacity remain unproven.

Validation for this task: documentation review and Git diff/status checks only; no application behavior changed, no new benchmark or Windows run. Prior onboarding evidence below is historical, not a fresh verification in this assessment.

## Prior onboarding baseline in this conversation

- Linux Python 3.11.18; `uv sync --frozen --extra dev --python 3.11` installed 67 locked dependencies. Added local `opencv-python-headless==4.13.0.92` and editable installation without altering manifest/lock.
- Actual av/torch/timm/onnxruntime imports passed; `torch.cuda.is_available()` returned false.
- 168 selected tests passed with seven unknown-marker warnings. Exact command, run from repository root:

```sh
.venv/bin/python -m pytest tests/test_api_hygiene.py tests/e2e/test_api_server_e2e.py tests/test_frame_capture.py tests/test_frame_diff_filter.py tests/test_telegram_formatter.py tests/test_person_matcher_match.py tests/test_person_matcher_storage.py tests/test_pyproject_install.py --tb=short
```

- Real HTTP API smoke passed health, unauthenticated 401 and authenticated events 200. Ephemeral token; loopback port 18092; process stopped afterward. No live inference/camera/Telegram validation.
- Full-suite collection failed on absent private `data/frames/FRONT/ground_truth.json` in `test_backtest_vm1.py` and `test_cross_diff_bbox_e2e.py`. A later broad run excluding these was interrupted during cleanup tests that write ~31 GB fixtures. It was not a passing full-suite run.
- Installer repeatability and API smoke were verified; `install_script` and `start_skill` saved to cloud configuration draft. Publication/new-device restoration was not verified.
- Local helpers/logs at `/workspace/camera-dev` and caches/venv are convenience artifacts, not portable repository deliverables. Ignored local `.env` contains sanitized placeholders; do not use it for deployment.

## Next task

Superseded by the authorized incremental implementation entry below. Hardware acceptance criteria and native Windows validation remain open.

Future entries should record scope, baseline commit, changed files, exact checks/results, unresolved issues and the next concrete action. Keep credentials, camera identifiers and private imagery out of these records.

## 2026-11-20 — incremental Windows 11 and MP4 implementation

Authorization now includes core compatibility changes and tests. Branch:
`feature/windows11-video-poc`, based on the assessment commit. Main has not
been merged into or changed; no commit/push performed. Original continuity
documents were untracked at the start and are included in the review changes.

Implemented:
- `infra/platform_service.py`: configured Windows service PID/restart using
  sc.exe, bounded state waits and explicit error results. No automatic wrapper
  installation. PID API and restart helper delegate on Windows; Darwin retains
  launchctl. Linux restart reports unsupported rather than running launchctl.
- Windows project/Chrome path defaults; Tailscale CLI detection with explicit
  address override retained; event JSON replacement uses os.replace.
- Health reads launchd plist via plistlib rather than plutil. Windows socket
  probes honor configured listener/API/MCP bind addresses; internal macOS Bash
  watchdog does not run on Windows. Windows listener uses optional Waitress.
- `scripts/replay_video.py`: MP4 timestamp sampling, four lossless frames,
  unique outputs/result.json, extraction-only mode and existing pipeline reuse.
  No camera/webhook servers; Telegram requires --notify. One sampled event per
  invocation; not a continuous video-event detector.
- Declared OpenCV/tzdata, optional recognition/windows extras, synchronized lock,
  missing matcher package discovery. Fixed numeric template placeholders.
- Sparse cleanup test files retain identical logical-size assertions without
  massive real allocation. Added 16 platform/replay tests.
- Windows operator/local acceptance guide in `deploy/windows/README.md`;
  README, AGENTS and context updated.

Validation:
1. Dependency sync with dev/windows/recognition extras succeeded. Real CLIP
   classes, av, cv2, onnxruntime and waitress import successfully on Linux.
2. Wheel build succeeded. Both previously omitted matcher packages import
   directly from the built wheel outside the checkout (isolated Python).
   This is not a clean Windows wheel/deployment acceptance test; model and
   config assets still need checkout/local provisioning.
3. Broad command:
   `.venv/bin/python -m pytest tests/ --ignore=tests/test_backtest_vm1.py --ignore=tests/test_cross_diff_bbox_e2e.py --tb=short`
   completed: **821 passed, 11 failed, 2 skipped**, 24 warnings. The two ignored
   modules cannot collect without private ground-truth frame data.
4. Of the 11 failures, one was the new Windows-path simulation importing native
   ONNX after changing platform.system. Fixed by initializing native libraries
   on the real host before reloading path policy. Final affected command:
   `.venv/bin/python -m pytest tests/test_windows_replay.py tests/test_health_reporter.py --tb=short`
   completed **35 passed** (16 new tests + 19 existing health tests).
   Earlier health/watchdog/privacy/replay recheck completed 44 passed before
   the last three platform test additions. No claim of a final green full suite.
5. Ten remaining broad-run failures require unavailable operator state:
   - MCP list-cameras test assumes nonempty camera configuration (1).
   - listener-status test assumes a running launchd listener PID (1).
   - post-merge tests read an absent, untracked .git/hooks/post-merge (3).
   - register-cameras tests assume a real local credentials file (5).
   No assertions were weakened and no fake production credentials/hooks were
   installed to make these pass.
6. Privacy, no-JPEG, no-image-resize, and orphan-module scanners passed.
   Ruff passed all changed production Python files and the new test file;
   existing cleanup test has an unrelated unused-import lint finding.
   git diff --check passed. No live camera, model downloads/inference, VLM,
   notifications or external service restart was performed.

Outstanding/local acceptance:
- Native Windows install and execution; NTFS permissions, paths with spaces,
  timezone, PyAV/FFmpeg camera decoding and Tailscale discovery.
- Install a separately reviewed Windows service wrapper; SCM lifecycle/recovery,
  permissions and sc.exe locale parsing. No service installation artifact is
  claimed as tested.
- macOS live launchd regression (cloud exercised existing mocked contracts).
- Real YOLO/VLM/re-ID/Telegram vertical slice; actual recognition flags and model
  artifacts. Synthetic mode remains test scaffolding.
- NVIDIA/DirectML provider support and acceleration are not implemented or
  verified. Existing CoreML/CPU provider selection and CPU embedding behavior
  remain unchanged. Target hardware/load/latency requirements remain open.
- Replay uses wall-clock evaluation time for night rules and does not simulate
  RTSP reconnection or continuous webhook timing.
- Full operator-dependent suites require appropriate isolated fixtures/services
  or future test-fixture cleanup. Private backtests require authorized data.

Next review: inspect the feature diff and Windows guide, then run extraction-only
MP4 evaluation on Windows 11 before enabling configured inference or notifications.

## 2026-11-20 — final review and controlled local handoff

User authorized complete diff review, relevant checks, commit and push on
feature/windows11-video-poc only. Reviewed all changed production modules,
replay/service helpers, tests, dependency/lock changes and continuity documents.
No blocking code issue or added credential/private imagery was found. Inference,
camera capture, VLM prompts and recognition/notification implementation files
remain unchanged. The review corrected stale documentation; no assertions or
application behavior were changed in this review pass.

Documentation corrections:
- AGENTS now reflects valid numeric defaults, logical-size cleanup fixtures,
  and explicit commit/push authorization.
- PROJECT_CONTEXT distinguishes historical findings from implemented dependency,
  packaging, hosting and file replacement changes.
- deploy/windows/README.md has a fresh-checkout PowerShell checklist, guarded
  .env creation, import/architecture checks, exact implemented replay flags,
  output verification and pre-inference blockers. Extraction-only is the first
  checkpoint; no live listener, model, service or notification is enabled.
- Git and uv must be installed first; native x64 Python 3.11, disk space,
  permitted downloads, native DLLs/codecs and writable/readable paths are local
  prerequisites. A Windows wrapper, camera/VLM credentials and GPU are not
  required for extraction-only. Do not assume Linux sparse-file allocation
  behavior on NTFS.

Verification performed again:
- Targeted command:
  .venv/bin/python -m pytest tests/test_windows_replay.py tests/test_health_reporter.py tests/test_cleanup.py tests/test_net_bind.py tests/test_paths.py tests/test_pyproject_install.py --tb=short
  Result: **78 passed**, including all 16 replay/platform cases and real MP4
  encoding/decoding in an unstubbed subprocess.
- Broad command:
  .venv/bin/python -m pytest tests/ --ignore=tests/test_backtest_vm1.py --ignore=tests/test_cross_diff_bbox_e2e.py --tb=short
  Result: **823 passed, 10 failed, 2 skipped**, 24 warnings. The ten failures
  are the same operator-state prerequisites documented above: nonempty camera
  configuration (1), a live launchd listener PID (1), an absent untracked
  post-merge hook (3), and local camera credentials (5). No new replay/platform
  application failure remains in this run. The two exclusions require absent
  private ground-truth frames, not a compatibility-code change.
- Ruff for all changed production Python and new tests; git diff --check;
  privacy, no-JPEG, no-image-resize and orphan-module scanners passed.
- uv lock --check passed. Lock changes are the declared dependencies and their
  transitives, including the transformers-compatible Hugging Face downgrade;
  wheel artifact URLs use files.pythonhosted.org. Principal native packages
  list Windows x64 wheels; metadata availability is not a Windows execution test.
- Inspected python -m scripts.replay_video --help; all documented options exist.
- GitHub read and feature-branch push dry run succeeded using existing platform
  authentication. No token was requested or exposed.

Next local actions: follow deploy/windows/README.md from a fresh Windows 11 x64
checkout; record commit/interpreter/media versions; confirm four lossless PNGs
and extract-only result.json; review that checkpoint before enabling configured
models or cameras. Native Windows/macOS service behavior and NVIDIA acceleration
remain unverified. The implementation still selects CoreML/CPU and has no new
CUDA/DirectML integration.

### Preserved implementation and push confirmation

Final reviewed implementation commit:
`4dab7dd3f2bfddc86e242eae0b9d51543c7f4bdc`
(`Add Windows compatibility adapters and camera-free MP4 replay`).

Push to `origin/feature/windows11-video-poc` succeeded; remote ls-remote
confirmed that exact implementation SHA. Remote main remained
`c60c34f14705e555f05121a931963dfd4425f42b`; no merge was performed.
This push-confirmation entry is a documentation-only follow-up commit, so the
branch tip will be newer than the implementation SHA. Resolve its exact tip with
`git log -1 --format=%H` or `git ls-remote origin refs/heads/feature/windows11-video-poc`.
The final chat handoff also reports that tip after push verification.

The branch is available for controlled Windows testing; a green Linux subset
does not certify Windows, macOS live supervision, NVIDIA, or model accuracy.
Start with the installation/import/extraction-only checkpoint in
deploy/windows/README.md. Keep --notify absent and do not start the live daemon.
