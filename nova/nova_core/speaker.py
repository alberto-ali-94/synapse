"""Local speaker enrollment/verification; imports perform no model loading."""
from nova_core.console import diagnostic
from pathlib import Path
import os

MODEL = 'speechbrain/spkrec-ecapa-voxceleb'
SAMPLE_RATE = 16000
MIN_SECONDS = 2.5
# Conservative starting value, NOT a calibrated authentication guarantee.
MATCH_THRESHOLD = .65
# A near miss is uncertain, not evidence that another speaker is present.
UNCERTAIN_MARGIN = .10


class VoiceUncertain(ValueError):
    """Require one more phrase at the beginning; never grant memory access."""


class SpeakerVerifier:
    def __init__(self, directory):
        import numpy as np
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        self.np, self.torch = np, torch
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'alberto.npz'
        self.encoder = EncoderClassifier.from_hparams(
            source=MODEL, savedir=str(self.directory / 'model'), run_opts={'device': 'cpu'})

    @property
    def enrolled(self):
        return self.path.is_file()

    def embedding(self, waveform):
        np = self.np
        signal = np.asarray(waveform, dtype=np.float32)
        if signal.ndim != 1 or len(signal) < SAMPLE_RATE * MIN_SECONDS:
            raise ValueError('Parla per almeno tre secondi per verificare la voce.')
        if not np.isfinite(signal).all() or float(np.sqrt(np.mean(signal ** 2))) < .003:
            raise ValueError('Audio insufficiente per verificare la voce.')
        speech_seconds = self.speech_seconds(signal)
        diagnostic(f'Qualita voce: durata={len(signal) / SAMPLE_RATE:.2f}s, '
              f'parlato={speech_seconds:.2f}s', flush=True)
        if speech_seconds < MIN_SECONDS:
            raise ValueError('Voce effettiva troppo breve: pronuncia una frase di almeno cinque secondi.')
        with self.torch.inference_mode():
            value = self.encoder.encode_batch(self.torch.from_numpy(signal).unsqueeze(0))
        value = value.detach().cpu().numpy().reshape(-1).astype(np.float32)
        norm = float(np.linalg.norm(value))
        if not norm or not np.isfinite(value).all():
            raise ValueError('Impronta vocale non valida.')
        return value / norm

    def speech_seconds(self, signal):
        """Count voiced 30 ms frames; do not confuse endpoint silence with speech."""
        import webrtcvad
        pcm = (signal * 32768).clip(-32768, 32767).astype(self.np.int16)
        vad = webrtcvad.Vad(2)
        frame = SAMPLE_RATE * 30 // 1000
        count = sum(vad.is_speech(pcm[start:start + frame].tobytes(), SAMPLE_RATE)
                    for start in range(0, len(pcm) - frame + 1, frame))
        return count * .03

    def enroll(self, embeddings):
        np = self.np
        if len(embeddings) != 3:
            raise ValueError('Sono necessari tre campioni vocali.')
        values = np.stack(embeddings)
        # Reject accidentally enrolling different speakers in the same profile.
        if float(np.min(values @ values.T)) < .65:
            raise ValueError('Campioni vocali incoerenti: ripeti la registrazione.')
        mean = values.mean(axis=0)
        mean /= np.linalg.norm(mean)
        temporary = self.path.with_suffix('.tmp')
        try:
            with temporary.open('wb') as target:
                os.chmod(temporary, 0o600)
                np.savez(target, embedding=mean, model=np.array(MODEL))
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def verify(self, waveform):
        self.last_score = None
        if not self.enrolled:
            diagnostic('Verifica voce: profilo assente; sessione ospite.', flush=True)
            return 'guest'
        value = self.embedding(waveform)
        with self.np.load(self.path, allow_pickle=False) as data:
            reference = data['embedding']
            if str(data['model']) != MODEL or reference.shape != value.shape:
                raise ValueError('Profilo vocale incompatibile: registralo nuovamente.')
            score = float(value @ reference)
        self.last_score = score
        result = ('alberto' if score >= MATCH_THRESHOLD else
                  'uncertain' if score >= MATCH_THRESHOLD - UNCERTAIN_MARGIN else 'guest')
        diagnostic(f'Verifica voce: esito={result}, similarita={score:.4f}, '
              f'soglia={MATCH_THRESHOLD:.4f}, durata={(len(waveform) if hasattr(waveform, "__len__") else 0) / SAMPLE_RATE:.2f}s', flush=True)
        if result == 'uncertain':
            raise VoiceUncertain('Voce incerta: pronuncia una frase diversa di almeno cinque secondi.')
        return result
