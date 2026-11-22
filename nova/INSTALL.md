# Nova installation

Target: macOS on Apple Silicon, Python 3.12. FRIDAY's private reference assets must already be available under `voices/friday/`; they are not distributed.

## Environment

With the existing environment:

```sh
uv pip install --python .venv/bin/python -r requirements.txt
```

For a new environment, create it first with `uv venv --python 3.12 .venv`. The requirements are a development-environment snapshot, not a cross-platform lock file. A clean-machine installation has not been validated.

Local conversation requires an Ollama service and `ollama pull qwen3.5:4b-mxfp8`. Keep the service running when selecting Local.

The first selected-mode startup may download Whisper, Qwen TTS, ECAPA-TDNN, E5 and (in Local) GLiClass Mini. Model downloads require Internet access; cached Local operation is intended to work offline. Cached snapshots are preferred for the new text models.

## Online credentials

Keep the existing `config.toml` and add a `JEV_API_KEY` entry. Alternatively copy `config.example.toml` to `config.toml` only when no configuration exists, then fill both keys:

```toml
API_KEY = "your OpenAI key"
JEV_API_KEY = "your TypeSafe key"
```

`TYPESAFE_API_KEY` can supply the TypeSafe key instead. Online requires account access and billing for GPT-6 Luna and Jev. Credentials are checked locally during preparation; the application never falls back to another mode. Cloud service calls have not been tested against a live paid account for this change.

## Launch

```sh
.venv/bin/python nova.py
.venv/bin/python nova.py online
.venv/bin/python nova.py local
```

Without an argument the window opens without loading models. Choose Online or Local; the microphone button stays disabled until preparation succeeds. Failed preparation restores mode selection. After successful preparation, restart Nova to change modes.

Italian, FRIDAY, local Qwen 8-bit, 0.9-second silence detection, a 60-second utterance cap and conservative speech streaming are internal defaults. Previous command-line options have been removed. Audio device IDs remain `MICROFONO` and `USCITA` in `nova_core/app.py`; inspect devices using `.venv/bin/python -m sounddevice` and grant macOS microphone permission when needed.

## Terminal output

Normal startup keeps concise API-call events (GPT, Jev or local Ollama), mode readiness, successful memory writes and errors. Timings, classification/voice diagnostics, ordinary warnings, stack traces and third-party initialization prints are hidden. Error and memory status remain visible in the window.

```sh
.venv/bin/python nova.py --verbose
.venv/bin/python nova.py online --verbose
.venv/bin/python nova.py local --verbose
```

Verbose mode applies to either GUI-selected mode and is preserved by the macOS launcher. Mode-selection buttons disappear as soon as a mode is selected, and reappear if preparation fails. Restart Nova to change a prepared mode.

## Enroll Alberto's voice

After preparation, click **Registra la mia voce**, confirm, and read each of the three displayed phrases slowly with the microphone normally used for Nova. No enrollment recording occurs on startup. Enrollment writes an embedding, not the raw recordings. Enrollment cannot establish the person's legal identity: use it only on the owner's trusted Mac.

Start a conversation and speak a complete first sentence. Verification runs only at the beginning, with one retry for insufficient audio. A missing profile or unmatched/uncertain voice gives a guest session with no personal-memory access. The initial similarity threshold is uncalibrated and must be evaluated with Alberto and other speakers. Voice recordings and cloned speech can defeat this prototype; speaker matching is not strong authentication.

Stop clears the verified identity, pending saves, conversational history and GPT continuation state. Start begins a fresh session while keeping the selected models loaded. Another speaker joining an already verified session is treated as Alberto until Stop.

## Private storage

`.private/speaker/` contains the speaker profile and its model assets. `.private/memory/` contains the live Qdrant archive; the retired vector-memory laboratory has been removed. Both are excluded from Git. `prova.wav`, the existing last-turn recording, is still overwritten per turn and remains on disk.

Back up `.private/` with Nova closed. No encryption-at-rest feature is implemented by Nova; protect the Mac account and disk. These private files are not distributed in the repository.
