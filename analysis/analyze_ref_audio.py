"""Measure a soundtrack: tempo/grid, how the sound lines up with the picture's cuts, harmonic vs percussive,
which pitch class dominates each bar (drone/chord changes), loudness. Two uses:
  1. a reference video's BGM -> numbers to copy when synthesizing (synth_bgm.py cues)
  2. our own render -> check that cuts land on transients (grid-synth acceptance: >=90% within 20 ms)

  python analyze_ref_audio.py <video-or-audio> [--cuts cuts.json | --kindex <frames>/index.json | --cues <proj>/cues.json]
                              [--out report_dir]
--cuts: JSON list of seconds. --kindex: index.json from scripts/ref_frames.py (content-change cuts, fps-quantized, so only
use it for references). --cues: take cut times from a cues.json (beats -> seconds via bpm/beatOffset).
Writes <out>/audio_report.json and audio_report.png (spectrogram, chroma, waveform with cuts and beats).
"""
import argparse, json, re, subprocess, tempfile
from pathlib import Path

import numpy as np

import common  # noqa: F401  (sets caches before librosa/numba)
import librosa
import librosa.display
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SR = 44100
HOP = 256
PC = "C C# D D# E F F# G G# A A# B".split()


def load(path):
    with tempfile.TemporaryDirectory() as d:
        w = Path(d) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SR), str(w)], check=True)
        y, _ = librosa.load(str(w), sr=SR)
    return y


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    s = r[r.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, s).group(1))  # noqa: E731
    return {"integrated_lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"),
            "true_peak_dbfs": g(r"Peak:\s+(-?[\d.]+) dBFS")}


def cut_times(a):
    if a.cuts:
        return [float(x) for x in json.loads(Path(a.cuts).read_text())]
    if a.cues:
        c = json.loads(Path(a.cues).read_text())
        per, off = 60 / c["bpm"], c.get("beatOffset", 0)
        return [off + b * per for b in c.get("cuts", [])]
    if a.kindex:
        j = json.loads(Path(a.kindex).read_text())
        it = j if isinstance(j, list) else j.get("frames", j)
        return [f.get("t_sec", f.get("start_sec")) for f in it]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--cuts"); ap.add_argument("--kindex"); ap.add_argument("--cues")
    ap.add_argument("--out")
    a = ap.parse_args()
    media = Path(a.media).resolve()
    out = Path(a.out) if a.out else media.parent
    out.mkdir(parents=True, exist_ok=True)
    y = load(media)
    dur = len(y) / SR

    tempo, bf = librosa.beat.beat_track(y=y, sr=SR, hop_length=HOP)
    beats = librosa.frames_to_time(bf, sr=SR, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    # backtrack to the energy rise = where the transient actually starts (what the ear locks to)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP, units="time", backtrack=True)
    H, P = librosa.effects.hpss(y)
    ch = librosa.feature.chroma_cqt(y=H, sr=SR, hop_length=512)
    per = 60 / tempo
    bars = []
    for k in range(int(dur / (4 * per)) + 1):
        i0, i1 = int(k * 4 * per * SR / 512), int((k + 1) * 4 * per * SR / 512)
        if i1 > i0 and i0 < ch.shape[1]:
            m = ch[:, i0:i1].mean(1)
            bars.append({"t": round(k * 4 * per, 2), "top": [PC[i] for i in np.argsort(m)[::-1][:3]]})

    rep = {"file": str(media), "duration": round(dur, 3), "tempo_bpm": round(tempo, 2),
           "beat_s": round(per, 4), "beats": np.round(beats, 3).tolist(), "onsets": np.round(on, 3).tolist(),
           "harmonic_percussive_ratio": round(float((H ** 2).sum() / max((P ** 2).sum(), 1e-12)), 2),
           "spectral_centroid_hz_median": int(np.median(librosa.feature.spectral_centroid(y=y, sr=SR))),
           "chroma_per_bar": bars, **loudness(media)}
    cuts = [c for c in cut_times(a) if c > 0.05]
    if cuts and len(on):
        d = np.array([np.min(np.abs(on - c)) for c in cuts])
        grid16 = per / 4
        rep["cuts"] = {"n": len(cuts), "nearest_onset_ms_median": round(float(np.median(d)) * 1000, 1),
                       "within_20ms": int((d <= 0.02).sum()), "within_100ms": int((d <= 0.1).sum()),
                       "on_16th_grid": int(sum(abs(c / grid16 - round(c / grid16)) * grid16 < 0.02 for c in cuts)),
                       "worst": [[round(c, 3), round(float(x) * 1000)] for c, x in sorted(zip(cuts, d), key=lambda z: -z[1])[:5]]}
    (out / "audio_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))

    fig, ax = plt.subplots(3, 1, figsize=(16, 9), sharex=True)
    S = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=4096, hop_length=512)), ref=np.max)
    librosa.display.specshow(S, sr=SR, hop_length=512, x_axis="time", y_axis="log", ax=ax[0]); ax[0].set_title("spectrogram")
    librosa.display.specshow(ch, sr=SR, hop_length=512, x_axis="time", y_axis="chroma", ax=ax[1]); ax[1].set_title("chroma (harmonic part)")
    t = np.arange(len(y)) / SR
    ax[2].plot(t, y, lw=0.3)
    for c in cuts: ax[2].axvline(c, color="r", lw=0.8)
    for b in beats: ax[2].axvline(b, color="g", lw=0.5, ls="--")
    ax[2].set_title("waveform  (red = picture cuts, green = detected beats)")
    plt.tight_layout(); plt.savefig(out / "audio_report.png", dpi=80)

    c = rep.get("cuts")
    print(f"{rep['duration']}s  {rep['tempo_bpm']} BPM  I={rep['integrated_lufs']} LUFS  TP={rep['true_peak_dbfs']} dBFS  "
          f"H/P={rep['harmonic_percussive_ratio']}" + (f"  cuts {c['n']}: median {c['nearest_onset_ms_median']} ms, "
          f"<=20ms {c['within_20ms']}/{c['n']}, <=100ms {c['within_100ms']}/{c['n']}, on 16th grid {c['on_16th_grid']}/{c['n']}" if c else ""))
    print(f"-> {out/'audio_report.json'}  {out/'audio_report.png'}")


if __name__ == "__main__":
    main()
