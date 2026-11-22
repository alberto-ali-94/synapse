"""Bounded speech endpointing; importing this module opens no audio devices."""
from collections import deque
import math
import queue
import threading
from time import monotonic

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2


class SpeechEndpoint:
    """Keep 300 ms pre-roll; require speech onset then a sustained pause."""
    def __init__(self, silence_seconds=.9, max_turn_seconds=60):
        self.silence_frames = math.ceil(silence_seconds * 1000 / FRAME_MS)
        self.max_frames = math.ceil(max_turn_seconds * 1000 / FRAME_MS)
        self.reset()

    def reset(self):
        self.history = deque(maxlen=10)
        self.onset = deque(maxlen=5)
        self.frames = []
        self.active = False
        self.speech_frames = 0
        self.quiet_frames = 0
        self.limit_reached = False

    def feed(self, frame, speech):
        if len(frame) != FRAME_BYTES:
            raise ValueError("Invalid VAD frame size")
        if not self.active:
            self.history.append((frame, speech))
            self.onset.append(speech)
            if len(self.onset) < 5 or sum(self.onset) < 3:
                return None
            self.active = True
            self.frames = [f for f, _ in self.history]
            self.speech_frames = sum(s for _, s in self.history)
        else:
            self.frames.append(frame)
            self.speech_frames += bool(speech)
        self.quiet_frames = 0 if speech else self.quiet_frames + 1
        self.limit_reached = len(self.frames) >= self.max_frames
        if self.quiet_frames >= self.silence_frames or self.limit_reached:
            if self.speech_frames < 6:  # Reject very short noises, not full questions.
                self.reset()
                return None
            return b"".join(self.frames)
        return None


def record_utterance(sd, app, config, vad_factory=None, device=0, prompt=None):
    """Capture only while listening; close input before inference/playback."""
    if vad_factory is None:
        import webrtcvad
        vad_factory = webrtcvad.Vad
    vad = vad_factory(2)
    endpoint = SpeechEndpoint(config.silence_seconds, config.max_turn_seconds)
    frames = queue.Queue(maxsize=100)  # At most 3 s of pending capture, never unbounded.
    overflow = threading.Event()

    def callback(indata, count, timing, status):
        if status or count != FRAME_SAMPLES:
            overflow.set()
        try:
            frames.put_nowait(bytes(indata))
        except queue.Full:
            overflow.set()

    stream = sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                               blocksize=FRAME_SAMPLES, device=device, latency="high",
                               callback=callback)
    started = monotonic()
    try:
        app._start_input(stream)
        app._publish("listen", prompt or config.text("Ti ascolto. Risponderò quando fai una pausa.",
                                           "Listening. I will respond when you pause."))
        while True:
            app._check_open()
            if overflow.is_set():
                raise RuntimeError(config.text("Acquisizione audio interrotta: riprova.", "Audio input overflow: please retry."))
            try:
                frame = frames.get(timeout=.1)
            except queue.Empty:
                app._check_open()
                if not stream.active or monotonic() - started > 3:
                    raise RuntimeError(config.text("Il microfono non fornisce audio.", "The microphone is not providing audio."))
                continue
            started = monotonic()
            result = endpoint.feed(frame, vad.is_speech(frame, SAMPLE_RATE))
            if result is not None:
                app._check_open()
                return result, endpoint.limit_reached
    finally:
        app._release_input(stream)
