# NOVA — Neural Omnimodal Virtual Agent

Nova is a macOS Apple Silicon voice-assistant prototype in Project Synapse. It supports Italian conversations, a local FRIDAY voice, session-level speaker verification and persistent personal memory. [Installation and enrollment](INSTALL.md).

## Start and choose a mode

```sh
.venv/bin/python nova.py
.venv/bin/python nova.py online
.venv/bin/python nova.py local
```

With no argument, the window loads without initializing models. Select Online or Local; the conversation button unlocks after preparation. An initialization error permits another selection. Changing a successfully prepared mode requires restarting the application. The `--verbose` switch restores timings, detailed diagnostics and warnings; other former command-line options are removed; their conservative settings remain internal defaults.

| Component | Local | Online |
|---|---|---|
| Conversation | Ollama Qwen3.5 4B MXFP8 | GPT-6 Luna API |
| Memory classification | GLiClass Multilang Mini | Jev API |
| Text embeddings | Multilingual E5 Small, CPU | Same local encoder |
| Memory storage | Local Qdrant | Same local Qdrant |
| Speaker verification | Local SpeechBrain ECAPA-TDNN | Same local verifier |
| Transcription | MLX Whisper Large V3 Turbo | Same local transcriber |
| Speech | Qwen3-TTS 1.7B Base 8-bit / private FRIDAY reference | Same local voice |

Online mode sends conversation text, extraction requests and retrieved memory context to OpenAI; classification text goes to TypeSafe. It requires both configured API keys. It does not send speaker-reference recordings to these APIs. Offline and online modes never switch automatically.

## Terminal output

Normal startup keeps concise API-call events (GPT, Jev or local Ollama), mode readiness, successful memory writes and errors. Timings, classification/voice diagnostics, ordinary warnings, stack traces and third-party initialization prints are hidden. Error and memory status remain visible in the window.

```sh
.venv/bin/python nova.py --verbose
.venv/bin/python nova.py online --verbose
.venv/bin/python nova.py local --verbose
```

Verbose mode applies to either GUI-selected mode and is preserved by the macOS launcher. Mode-selection buttons disappear as soon as a mode is selected, and reappear if preparation fails. Restart Nova to change a prepared mode.

## Conversation identity

Use **Registra la mia voce** to enroll three samples explicitly through the window. The first utterance of each conversation is compared with Alberto's local profile. Verification is not repeated during that conversation. Guests and uncertain speakers can converse but cannot invoke personal-memory classification, retrieval, extraction or saving. Stop clears identity, pending memory proposals, conversation history and GPT continuation state. A new Start requires verification again; the models remain loaded.

The owner must enroll on their trusted device. The voice threshold is a provisional operating value, not a measured security guarantee. Recorded/cloned voices and another person taking over an authenticated conversation remain limitations. Guest and owner conversations do not share application-side context, but provider-side retention of previous cloud requests is separate.

## Personal memory

The live archive is under `.private/memory/`, separate from the student experiment. Memories contain an ID, text, type, domain, owner, active status, encoder name, provenance and timestamp. The owner ID is assigned by application policy, never by a model. Verified session identity is supplied to the conversational model independently of database availability; direct name questions use that session identity without a classifier or database lookup. Query filters enforce owner and active status; confidently classified type/domain narrow retrieval. Counting uses exact structured filters.

Explicit remember requests produce validated atomic candidates; the classifier assigns their categories. Implicit facts are proposed and require a subsequent affirmative reply before saving. A rejected/ambiguous extraction is not saved. Only user messages are candidate sources; assistant answers are not stored as personal facts. The application commits saved candidates only after the final cancellation check. Exact duplicate text uses the same ID.

An LLM extracts candidate text because classification alone cannot split a conversation into atomic memories. Online extraction uses an independent, non-stored GPT request with a strict JSON schema; Local extraction uses the configured Ollama model. Category and intent scores use provisional thresholds, not calibrated probabilities. Deterministic consent rules complement the local zero-shot classifier.

Retrieval uses normalized E5 query embeddings and cosine ranking of up to four candidates. There is no uncalibrated absolute score cutoff: a lower cosine score can still be a correct factual match. If topical filters produce no candidates, the search may relax type/domain while always retaining owner, active-state and encoder filters. The conversational model must use only explicit candidate facts that answer the question, and say when no candidate provides an answer. Candidate ranking does not guarantee relevance. Retrieved content is data, not instructions.

Automatic semantic deduplication, contradiction resolution, expiration, memory editing/deletion controls, and encryption at rest are not implemented. Conflicting facts can coexist: these require a later memory-management increment before relying on automatic updates. Explicit requests whose extraction/classification fails do not produce a successful-save acknowledgement. The interface shows owner-only memory status (pending confirmation, saved to disk, retrieved candidates or a sanitized component/error code); terminal diagnostics identify the failing stage without logging credentials or raw provider bodies.

## Audio and lifecycle

Local VAD records mono 16 kHz PCM, with a 0.9-second final pause and a 60-second cap. The latest utterance remains in `prova.wav`. FRIDAY uses conservative 0.64-second synthesis chunks and an initial playback buffer. Online responses stream complete sentences to synthesis. Stop aborts audio; cancellation is checked before committing replies and memories. Native synthesis/other blocking model operations cannot always be interrupted mid-computation.

There is one model-owning worker; enrollment, conversation and initialization do not run concurrently. CPU classifiers and embeddings add memory and latency; a full integrated conversation peak has not yet been measured. Do not infer required RAM from downloaded weight sizes.

## Validation and scope

Hardware-free regression tests cover mode selection, session reset, guest isolation, pending confirmations, cancellation, extraction validation and existing audio/streaming behavior. Local model loading and temporary-database persistence have been exercised with synthetic data. One authorized synthetic Jev request and two authorized synthetic GPT extraction requests verified the cloud request formats: legacy JSON mode failed with HTTP 400, while strict JSON schema succeeded. Confirmed persistence across sessions and guest exclusion were checked locally with synthetic data. Actual owner/guest voice acceptance and a full spoken end-to-end cloud conversation still require user validation.

Wake word activation, tool execution, Atlas integration and remote access remain future work. FRIDAY reference assets, runtime environments, tests and student experiments are local-only and are not distributed in a source-only checkout. See [INSTALL.md](INSTALL.md).
