# NOVA — Neural Omnimodal Virtual Agent

Nova is the voice assistant in Project Synapse. It runs on macOS Apple Silicon with Italian speech, Online and Local conversation modes, speaker verification and a persistent personal-memory archive.

## Setup and launch

Follow [INSTALL.md](INSTALL.md) for the Python environment, model downloads, audio devices and credentials. Speech synthesis requires the private FRIDAY reference audio and transcript under `voices/friday/`; these assets are not distributed.

From `nova/`:

```sh
.venv/bin/python nova.py
.venv/bin/python nova.py online
.venv/bin/python nova.py local
```

With no argument, the window opens before model loading. Select **Online** or **Local** to prepare the pipeline. Conversation controls become available when preparation finishes. A failed initialization restores mode selection; changing a prepared mode requires restarting Nova.

| Component | Online | Local |
|---|---|---|
| Conversation | GPT-6 Luna API | Ollama `qwen3.5:4b-mxfp8` |
| Memory classification | Jev API | GLiClass Multilang Mini on CPU |
| Transcription | MLX Whisper Large V3 Turbo | Same |
| Speech | Qwen3-TTS 1.7B Base 8-bit with FRIDAY reference | Same |
| Embeddings | Multilingual E5 Small, 384 dimensions, CPU | Same |
| Storage | Embedded local Qdrant | Same |
| Speaker verification | SpeechBrain ECAPA-TDNN on CPU | Same |

Online requires OpenAI and TypeSafe credentials. Conversation text, extraction requests and retrieved context go to OpenAI; classification text goes to TypeSafe. Microphone transcription, voice synthesis, speaker verification and database storage run locally. Speaker-reference recordings are not sent to either API.

Local requires a running Ollama service. Download the models before offline use. Nova does not switch modes automatically when a provider is unavailable.

## Conversation and voice enrollment

1. Prepare a mode and select **Registra la mia voce** to enroll the owner.
2. Confirm enrollment and read the three displayed phrases using the usual microphone.
3. Start a conversation and speak a complete opening sentence.
4. Stop to end the session. Starting again repeats speaker verification without reloading the prepared models.

The current owner profile is Alberto. Enrollment stores a normalized voice embedding on the Mac. Initial verification requires at least 2.5 seconds of detected speech; a short or uncertain sample prompts one additional phrase. The first question is retained while verification completes.

Verified owner sessions can retrieve and save personal memories. Missing or unmatched profiles fall back to a guest conversation. Guests do not invoke personal-memory classification, extraction, retrieval or saving. Questions about the verified user's name use session identity directly.

Stop resets identity, conversation history, pending memory proposals and GPT continuation state. Verification runs at the start of each conversation, not continuously: another person speaking during an already verified session inherits that session's access.

Speaker matching is a prototype access check. Its threshold has not been calibrated across genuine and other speakers, and it does not defend against recorded or cloned voices. Enroll only on the owner's trusted Mac.

## Persistent memory

Nova stores personal facts in `.private/memory/`, using Qdrant and normalized E5 embeddings. Each record includes text, type, domain, owner, active state, encoder version, source hash and update time.

### Saving

Explicit requests to remember something can save validated facts directly. Facts proposed from other statements require an affirmative follow-up before writing. Extraction produces at most three atomic memories; the classifier assigns type and domain. Ambiguous or invalid candidates are rejected, and assistant responses are not used as source facts.

The UI reports successful persistence after the database write completes. A final cancellation check precedes the write. Repeated text shares a stable ID; semantically equivalent wording can still create separate records.

### Retrieval

Search uses `query:` and `passage:` E5 prefixes, cosine ranking and up to four candidates. Filters always retain the owner, active state and encoder; type/domain restrictions can be relaxed if they return no candidates. Counts use exact database filters.

Retrieved text is supplied as context for the current question. Similarity ranks candidates; it does not establish that a memory answers the question. There is no fixed, uncalibrated score cutoff. Ownership and permissions come from application code, not generated or retrieved text.

Memory correction, deletion controls, expiration, semantic deduplication, contradiction resolution and encryption at rest are not implemented. Conflicting facts can coexist.

## Audio and session handling

Voice activity detection records mono 16 kHz PCM with a 0.9-second final pause and a 60-second turn limit. The latest recording is written to `prova.wav`. Whisper receives the captured waveform directly.

FRIDAY uses Qwen3-TTS with 0.64-second synthesis chunks and an initial playback buffer. Online responses stream complete sentences into synthesis. Stop aborts audio and cancels further turn processing; an active native model operation may still need to finish before the worker can return.

One worker owns the models and serializes preparation, enrollment and conversation. A full integrated peak-memory measurement is still pending.

## Logging

Normal terminal output shows mode readiness, API-call events, successful memory writes and errors. The window displays conversation, identity and memory status.

Use `--verbose` for timings, warnings and detailed diagnostics:

```sh
.venv/bin/python nova.py --verbose
.venv/bin/python nova.py online --verbose
.venv/bin/python nova.py local --verbose
```

The flag also applies when choosing the mode in the window.

## Local data

| Location | Contents |
|---|---|
| `voices/friday/` | Private voice reference audio and transcript |
| `.private/speaker/` | Owner voice profile and speaker-model assets |
| `.private/memory/` | Persistent personal-memory database |
| `prova.wav` | Latest microphone recording, overwritten each turn |
| `config.toml` | Private API configuration |

These paths are excluded from version control. Close Nova before backing up `.private/` and protect the files with the Mac account and disk security settings.

## Validation and development

Local regression checks cover session reset, guest isolation, memory confirmations, extraction validation, cancellation and audio streaming. Model loading and persistence across database reopen have been exercised locally; cloud diagnostics have checked Jev access and GPT structured extraction.

Full spoken cross-conversation memory validation and owner/guest acceptance testing after the latest verification changes remain pending. Wake word activation, external tool execution, Atlas integration and remote access are planned.
