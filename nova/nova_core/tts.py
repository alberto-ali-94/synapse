"""Qwen speech adapter. Importing this module loads no model or audio runtime."""
from nova_core.console import diagnostic
from pathlib import Path
from time import perf_counter
import wave
from nova_core.paths import ROOT_DIR

MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"


class FridayVoice:
    """One model and local runtime assets, owned by Nova's single worker."""

    def __init__(self, reference_dir=None, *, streaming_interval=.64, cache_speaker=True):
        if streaming_interval not in (.32, .64):
            raise ValueError("Speech chunks must be 0.32 or 0.64 seconds")
        self.streaming_interval = streaming_interval
        self.cache_speaker = cache_speaker
        reference_dir = Path(reference_dir) if reference_dir is not None else ROOT_DIR / "voices" / "friday"
        reference = reference_dir / "reference.wav"
        transcript = reference_dir / "reference.txt"
        if not reference.is_file() or not transcript.is_file():
            raise FileNotFoundError(f"FRIDAY reference audio or transcript missing in {reference_dir}")
        self.reference_text = transcript.read_text(encoding="utf-8").strip()
        if not self.reference_text:
            raise ValueError("FRIDAY reference transcript is empty")
        with wave.open(str(reference), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getframerate() != 24000 or wav.getsampwidth() != 2 or not wav.getnframes():
                raise ValueError("FRIDAY reference must be a nonempty mono 24 kHz PCM16 WAV")

        import mlx.core as mx
        import numpy as np
        from mlx_audio.tts.utils import load_model
        from mlx_audio.utils import load_audio
        self.mx, self.np = mx, np
        self.model = load_model(MODEL_ID)
        if getattr(self.model.config, "tts_model_type", None) != "base":
            raise ValueError("FRIDAY requires the Qwen3-TTS Base checkpoint")
        if not self.model.speech_tokenizer.has_encoder:
            raise ValueError("Qwen reference audio encoder is missing")
        self.reference_audio = load_audio(str(reference), sample_rate=self.model.sample_rate)
        mx.eval(self.reference_audio)
        self._speaker_embedding = None
        extract = getattr(self.model, "extract_speaker_embedding", None)
        if extract is not None:
            # Instance-local adapter, not a change to mlx_audio. Only reuse the
            # immutable reference owned by this voice; other inputs bypass it.
            def cached_embedding(audio, sr=24000):
                if not self.cache_speaker or audio is not self.reference_audio or sr != 24000:
                    return extract(audio, sr=sr)
                if self._speaker_embedding is None:
                    start = perf_counter()
                    value = extract(audio, sr=sr)
                    mx.eval(value)
                    self._speaker_embedding = value
                    diagnostic(f"Preparazione impronta FRIDAY (una volta): {perf_counter()-start:.3f} s", flush=True)
                return self._speaker_embedding
            self.model.extract_speaker_embedding = cached_embedding

    def generate(self, text, *, language):
        if language not in ("Italian", "English"):
            raise ValueError("Unsupported speech language")
        self.mx.random.seed(42)
        # Reference codes and speaker features are reused; text prefill is new.
        for result in self.model.generate(
            text, lang_code=language,
            ref_audio=self.reference_audio, ref_text=self.reference_text,
            max_tokens=1024, verbose=False, stream=True, streaming_interval=self.streaming_interval,
        ):
            self.mx.eval(result.audio)
            rate = int(result.sample_rate)
            if rate <= 0 or rate != result.sample_rate:
                raise ValueError("Invalid Qwen speech sample rate")
            audio = self.np.array(result.audio, dtype=self.np.float32, copy=True, order="C")
            if audio.ndim != 1 or not self.np.isfinite(audio).all():
                raise ValueError("Invalid Qwen speech audio")
            yield audio, rate
