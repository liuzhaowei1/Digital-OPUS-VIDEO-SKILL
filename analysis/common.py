"""Shared paths for the opus-video music analysis (import FIRST: sets model caches).

Layout per project (<proj> = $OPUS_HOME/<date>_<slug>, OPUS_HOME defaults to ~/opus-video):
  <proj>/public/audio/<song>        the song (what the video plays)
  <proj>/.analysis/mix.wav          gapless 44.1 kHz decode = the time reference
  <proj>/.analysis/stems/*.wav      Demucs stems of mix.wav (same timeline, no offset)
  <proj>/.analysis/work/            features, emissions, QA plots
  <proj>/public/data/audio.json     beats / downbeats / sections / envelopes / onsets  (engine: AudioData)
  <proj>/public/data/lyrics.json    word-timed lyrics                                (engine: Lyrics)
Models download once into $OPUS_HOME/_models (shared by all projects, kept; ~1.6 GB, +3 GB with whisper).
JIT/font caches (numba, matplotlib) go to ~/.cache/opus-video and are safe to delete.
"""
import os
from pathlib import Path

OPUS_HOME = Path(os.environ.get("OPUS_HOME", Path.home() / "opus-video"))
MODELS = Path(os.environ.get("OPUS_MODELS", OPUS_HOME / "_models"))
JITCACHE = Path(os.environ.get("OPUS_JITCACHE", Path.home() / ".cache" / "opus-video"))
for var, base, sub in [("TORCH_HOME", MODELS, "torch"), ("HF_HOME", MODELS, "hf"), ("HF_HUB_CACHE", MODELS, "hf/hub"),
                       ("HUGGINGFACE_HUB_CACHE", MODELS, "hf/hub"),
                       ("MPLCONFIGDIR", JITCACHE, "mpl"), ("NUMBA_CACHE_DIR", JITCACHE, "numba")]:
    os.environ.setdefault(var, str(base / sub))
    (base / sub).mkdir(parents=True, exist_ok=True)

SR = 44100


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.an = self.root / ".analysis"
        self.mix = self.an / "mix.wav"
        self.stems = self.an / "stems"
        self.work = self.an / "work"
        self.data = self.root / "public" / "data"
        for d in (self.an, self.stems, self.work, self.data):
            d.mkdir(parents=True, exist_ok=True)

    def load_mix(self, sr=SR, mono=True):
        import librosa
        y, _ = librosa.load(str(self.mix), sr=sr, mono=mono)
        return y

    def load_stem(self, name, sr=SR, mono=True):
        import soundfile as sf
        import numpy as np
        y, s = sf.read(self.stems / f"{name}.wav", dtype="float32", always_2d=True)
        y = y.mean(axis=1) if mono else y.T
        if sr and sr != s:
            import librosa
            y = librosa.resample(y, orig_sr=s, target_sr=sr) if mono else np.stack([librosa.resample(c, orig_sr=s, target_sr=sr) for c in y])
        return y
