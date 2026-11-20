# Working agreement

This repository is being evaluated as a proof of concept for eventual Windows deployment. Read `PROJECT_CONTEXT.md` and `PROGRESS.md` before starting work. Source code is authoritative when historical documentation disagrees.

## Scope and continuity

- Current authorization: incremental Windows 11 compatibility and MP4 replay implementation with tests, preserving macOS and pipeline behavior. Work on feature/windows11-video-poc; do not merge main. The current user request authorizes review, commit and push to that branch after checks.
- Follow the staged plan in `PROJECT_CONTEXT.md`; document implemented changes separately from unverified hardware behavior.
- Use the existing checkout. Cloud tasks are isolated; do not create a Git worktree unless explicitly requested.
- Inspect Git status first and preserve existing user changes. Keep changes focused; do not commit or push unless requested.
- Update `PROGRESS.md` after meaningful work: date, scope, files changed, exact validation and results, blockers, next step. Update context when architectural facts or decisions change. Distinguish proposals from implemented behavior.
- These tracked Markdown documents are the cross-task knowledge source. External helpers, virtual environments, live processes, and cloud snapshots are machine-specific; do not assume they exist on another device. Documents must be committed/transferred through the user's workflow to reach another checkout.

## Development baseline

- Python 3.11 is the documented baseline; manifest permits >=3.11. Use `.venv/bin/python` on Unix and `.venv\Scripts\python.exe` on Windows.
- Prefer `uv sync --frozen --extra dev --python 3.11`. Current install: `uv sync --frozen --extra dev --extra windows --extra recognition --python 3.11`. Omit optional extras if not required. See `deploy/windows/README.md` for PowerShell and deployment boundaries.
- Keep manifest and lock changes intentional and synchronized; preserve model checksum verification.
- Inspect local configuration before running. `.env.example` now supplies numeric night-classifier defaults 0.40 and 1.5; the ignored local `.env` must be inspected separately. It still contains credential placeholders and is not deployment configuration.
- Configuration can be read at import time. Load test/local environment before importing `infra` and use explicit project/data/log directories for isolated runs.

## Validation boundaries

Use the representative command recorded in `PROGRESS.md`. Do not claim the full suite is green: two backtests require absent private frames. Cleanup fixtures have large logical sizes but use sparse truncation on Linux; do not assume NTFS allocates them sparsely. Select tests intentionally; report exclusions and interruptions.

Pytest fixtures stub PyAV and suntime and default live embedders off. Passing tests do not establish real decoding, GPU acceleration, model accuracy, or Windows compatibility. Verify actual runtime providers and real media separately when authorized and equipped.

## Application constraints

- Preserve lossless evidence/artifact policy, model SHA-256 verification, motion-gate behavior, and routing contracts. Consult existing image/privacy scanners before changing processing.
- Never bypass TLS, signature, or checksum verification. Do not replace missing private fixtures with invented passing data.
- Never copy secrets, raw environment dumps, camera addresses, property imagery, biometric registries, or tokens into documentation or logs. Use secure local/platform configuration.
- Do not contact cameras, alter camera configuration, send Telegram messages, or restart external services as part of a read-only assessment. Live checks need explicit scope and suitable credentials.
- GPU-enabled PyTorch does not accelerate ONNX Runtime automatically. Current YOLO provider selection is CoreML/CPU; embedder code does not explicitly move models/tensors to CUDA.
- Windows adapters and replay are implemented but need native Windows acceptance. Queueing and GPU support remain future work; cloud mocks do not prove Windows/GPU compatibility.
