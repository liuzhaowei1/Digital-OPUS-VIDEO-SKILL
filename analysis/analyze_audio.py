"""Music analysis -> <project>/public/data/audio.json (the engine's AudioData).

Generalised from mexicat/pdoom-video analysis/analyze.py (MIT). Verbatim: band filters, RMS envelopes,
one-pole smoothing, band onset detection, kick/snare/hat classification from the drums stem. Changed for
any song: tempo search around librosa's estimate (not a fixed 125-138 BPM), bar phase chosen automatically
(kick on 1/3, snare on 2/4, chord changes on 1) instead of by hand, sections found by structural
segmentation snapped to downbeats instead of a hand-written bar table, vocal features computed inline.
Automatic sections are a first draft (verse/chorus with similar timbre merge); with lyrics, cut on lyric
lines instead (engine timeline.ts). Assumes a constant tempo (true of most produced/AI-generated songs); the log prints the kick residual so
drift shows up.

  python analyze_audio.py <project_dir> [--bpm 132] [--sections 8] [--plots]
"""
import common
import json
import math
import sys

import numpy as np
import librosa
from scipy.ndimage import maximum_filter1d, median_filter, uniform_filter1d
from scipy.signal import butter, find_peaks, sosfiltfilt

SR = 44100
FPS = 100


# ---------------------------------------------------------------------------
def band_sos(lo, hi, sr):
    if lo and hi:
        return butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    if hi:
        return butter(4, hi, btype="low", fs=sr, output="sos")
    return butter(4, lo, btype="high", fs=sr, output="sos")


def frame_rms(x, sr, fps=FPS, win=2048):
    hop = sr / fps
    n = int(math.ceil(len(x) / sr * fps))
    pad = np.pad(x, (win // 2, win // 2 + int(hop) + 2))
    idx = (np.arange(n) * hop).astype(int)
    c = np.concatenate([[0.0], np.cumsum(pad.astype(np.float64) ** 2)])
    e = (c[idx + win] - c[idx]) / win
    return np.sqrt(np.maximum(e, 0))


def smooth_env(x, fps=FPS, attack=0.010, release=0.090):
    """One-pole follower: fast attack, slower release (visual friendly)."""
    aa = math.exp(-1 / (attack * fps))
    ar = math.exp(-1 / (release * fps))
    y = np.empty_like(x)
    s = 0.0
    for i, v in enumerate(x):
        a = aa if v > s else ar
        s = a * s + (1 - a) * v
        y[i] = s
    return y


def norm01(x, pct=99.0):
    ref = np.percentile(x, pct)
    return np.clip(x / (ref + 1e-12), 0, 1)


# ---------------------------------------------------------------------------
def band_onsets(x, sr, lo, hi, win=0.010, hop_s=0.002, min_gap=0.08, rel_db=10.0,
                decay_win=None):
    """Onsets in a frequency band: steepest rise of the band's log-energy
    envelope; strength = peak dB rise.  Returns (times, rise_db[, decay_db])."""
    xb = sosfiltfilt(band_sos(lo, hi, sr), x)
    h = int(hop_s * sr)
    w = int(win * sr)
    e = np.convolve(xb.astype(np.float64) ** 2, np.ones(w) / w, mode="same")[::h]
    db = 10 * np.log10(e + 1e-10)
    fps = sr / h  # exact frame rate (h is an integer number of samples)
    d = np.diff(db, prepend=db[0])
    d = uniform_filter1d(d, 3)
    # rise over ~20 ms
    lag = int(0.02 * fps)
    rise = db - np.concatenate([np.full(lag, db[0]), db[:-lag]])
    floor = median_filter(db, int(1.0 * fps) | 1)
    pk, _ = find_peaks(rise, height=rel_db, distance=int(min_gap * fps))
    times, strength = [], []
    for p in pk:
        a = max(0, p - lag)
        # attack time: steepest slope within the rise window
        q = a + int(np.argmax(d[a:p + 1]))
        peak_db = db[p:p + int(0.03 * fps)].max()
        if peak_db < floor[p] + 3:
            continue
        times.append(q / fps)
        strength.append(peak_db)
    return np.array(times), np.array(strength)


def drum_onsets(d, sr, grid_P, grid_off):
    """Kick / snare / hat onsets from the drums stem."""
    # KICK: <120 Hz
    kt, kdb = band_onsets(d, sr, None, 120, win=0.012, min_gap=0.15, rel_db=12)
    # SNARE (and the clap-like snare of the quiet chorus): candidates are
    # 1.5-5 kHz attacks; a snare has a long noisy 0.5-5 kHz tail 40-120 ms after
    # the attack.  Keep candidates whose tail is within 8 dB of the loudest tail
    # in +-2.5 s and within 25 dB of the song-wide level (rejects stem bleed).
    # Kick-only beats / hats have tails 12-30 dB lower.
    st, sdb = band_onsets(d, sr, 1500, 5000, win=0.010, min_gap=0.15, rel_db=10)
    xb = sosfiltfilt(band_sos(500, 5000, sr), d)
    e = np.sqrt(np.convolve(xb.astype(np.float64) ** 2, np.ones(441) / 441, mode="same"))
    tail = np.array([20 * np.log10(e[int((t + 0.04) * sr):int((t + 0.12) * sr)].mean() + 1e-9) for t in st])
    rel = np.array([tail[i] - tail[np.abs(st - st[i]) < 2.5].max() for i in range(len(st))])
    thr = np.percentile(tail, 95) - 25
    keep = (rel > -8) & (tail > thr)
    st, sdb, stail = st[keep], sdb[keep], tail[keep]
    # HAT: >7 kHz, short; drop those coinciding with snares (snare noise also
    # reaches 7k+)
    ht, hdb = band_onsets(d, sr, 7000, None, win=0.006, min_gap=0.06, rel_db=9)
    # (and those within 30 ms of a kick: the kick's beater click reaches 10 kHz)
    for other, gap in ((st, 0.04), (kt, 0.03)):
        if len(other) and len(ht):
            dist = np.min(np.abs(ht[:, None] - other[None, :]), axis=1)
            keep = dist > gap
            ht, hdb = ht[keep], hdb[keep]
    return (kt, kdb), (st, stail), (ht, hdb), thr


def strength01(db_vals, lo_pct=5, hi_pct=95):
    if len(db_vals) == 0:
        return db_vals
    lo, hi = np.percentile(db_vals, lo_pct), np.percentile(db_vals, hi_pct)
    return np.clip((db_vals - lo) / (hi - lo + 1e-9) * 0.8 + 0.2, 0, 1)




def onset_env(x, sr):
    y = librosa.resample(x, orig_sr=sr, target_sr=22050)
    o = librosa.onset.onset_strength(y=y, sr=22050, hop_length=32, lag=1, max_size=1)
    return o / (np.percentile(o, 99) + 1e-9)


def fit_grid(drums, mix, sr, duration, bpm_hint=None):
    """Constant-tempo grid: tempo/phase search on drum+mix onset envelopes around librosa's estimate,
    then phase refinement on kick attacks (as in the original)."""
    o = onset_env(mix, sr)
    if np.abs(drums).max() > 1e-3:
        o = o + onset_env(drums, sr)
    ofps = 22050 / 32
    if bpm_hint:
        bpm0 = float(bpm_hint)
    else:
        bpm0 = float(np.atleast_1d(librosa.feature.tempo(y=librosa.resample(mix, orig_sr=sr, target_sr=22050), sr=22050))[0])
        while bpm0 < 70: bpm0 *= 2
        while bpm0 > 180: bpm0 /= 2

    def score(P, off):
        ts = off + P * np.arange(int(duration / P) + 1)
        idx = np.round(ts * ofps).astype(int)
        idx = idx[(idx > 2) & (idx < len(o) - 2)]
        return np.maximum.reduce([o[idx - 1], o[idx], o[idx + 1]]).mean()

    best = (0, None, None)
    for bpm in np.arange(bpm0 * 0.96, bpm0 * 1.04, 0.02):
        P = 60 / bpm
        for off in np.arange(0, P, 0.004):
            s = score(P, off)
            if s > best[0]:
                best = (s, bpm, off)
    _, bpm, off = best
    for b2 in np.arange(bpm - 0.02, bpm + 0.02, 0.001):
        P = 60 / b2
        for o2 in np.arange(off - 0.01, off + 0.01, 0.001):
            s = score(P, o2)
            if s > best[0]:
                best = (s, b2, o2)
    _, bpm, off = best
    P = 60 / bpm
    kick_t, _ = band_onsets(drums, sr, None, 120, win=0.012, min_gap=0.2, rel_db=12) if np.abs(drums).max() > 1e-3 else (np.array([]), None)
    res = np.array([])
    if len(kick_t):
        n = np.round((kick_t - off) / P)
        res = kick_t - (off + n * P)
        res = res[np.abs(res) < 0.06]
        if len(res) >= 8:
            off = off + float(np.median(res))
    off = off - P * math.floor(off / P)
    return bpm, P, off, res


def bar_phase(beats, P, kicks, snares, mix, sr):
    """Which beat index mod 4 is the downbeat: kicks on 1 and 3, snares on 2 and 4, harmonic change on 1.
    Returns (phase, scores) — close scores mean the phase is a guess (check the QA plot)."""
    def near(ts, i_mod):
        if len(ts) == 0: return 0.0
        tot = 0.0
        for k, b in enumerate(beats):
            if k % 4 in i_mod and np.min(np.abs(ts - b)) < 0.05: tot += 1
        return tot
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=librosa.resample(mix, orig_sr=sr, target_sr=22050), sr=22050, hop_length=hop)
    fr = np.clip(np.round(beats * 22050 / hop).astype(int), 0, chroma.shape[1] - 1)
    bc = chroma[:, fr]
    change = np.r_[0, np.linalg.norm(np.diff(bc, axis=1), axis=0)]
    scores = []
    for ph in range(4):
        s = 0.0
        s += near(kicks, {ph % 4, (ph + 2) % 4}) - near(kicks, {(ph + 1) % 4, (ph + 3) % 4}) * 0.5
        s += near(snares, {(ph + 1) % 4, (ph + 3) % 4}) - near(snares, {ph % 4, (ph + 2) % 4}) * 0.5
        s += 3.0 * change[np.arange(len(beats)) % 4 == ph].mean() / (change.mean() + 1e-9) * len(beats) / 16
        scores.append(round(float(s), 2))
    return int(np.argmax(scores)), scores


def find_sections(mix, sr, downbeats, duration, k=None):
    """Structural segmentation on bar-synchronous chroma + MFCC, boundaries on downbeats."""
    y = librosa.resample(mix, orig_sr=sr, target_sr=22050)
    hop = 512
    feat = np.vstack([librosa.feature.chroma_cqt(y=y, sr=22050, hop_length=hop),
                      librosa.util.normalize(librosa.feature.mfcc(y=y, sr=22050, hop_length=hop, n_mfcc=13), axis=1)])
    bars = np.clip(np.round(np.asarray(downbeats) * 22050 / hop).astype(int), 0, feat.shape[1] - 1)
    bars = np.unique(np.r_[0, bars, feat.shape[1]])
    sync = librosa.util.sync(feat, bars, aggregate=np.median)
    k = k or int(np.clip(round(duration / 12), 4, 16))   # pdoom: 156 s -> 13 (hand-labelled: 14)
    k = min(k, sync.shape[1])
    bounds = librosa.segment.agglomerative(sync, k)
    times = [0.0] + [float(bars[b] * hop / 22050) for b in bounds if b > 0] + [duration]
    times = sorted(set(round(t, 3) for t in times))
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    # merge sections shorter than a bar into the next one
    min_len = (downbeats[1] - downbeats[0]) if len(downbeats) > 1 else 2.0
    times = [t for i, t in enumerate(times) if i == 0 or i == len(times) - 1 or (times[i] - times[i - 1] >= min_len * 0.9)]
    secs = []
    for i in range(len(times) - 1):
        a, b = times[i], times[i + 1]
        e = float(rms[int(a * 22050 / hop):max(int(a * 22050 / hop) + 1, int(b * 22050 / hop))].mean())
        secs.append(dict(name=f"S{i + 1:02d}", start=a, end=b, energy=e))
    mx = max(s["energy"] for s in secs) or 1
    for s in secs: s["energy"] = round(s["energy"] / mx, 3)
    return secs


def vocal_feats(v, sr):
    """Vocal-stem features (5 ms hop) for vocal note onsets — inline version of the original vocal_feats.py."""
    y = librosa.resample(v, orig_sr=sr, target_sr=22050)
    HOP = 110
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=HOP, center=True)[0]
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=HOP, center=True)) ** 2
    logmel = librosa.power_to_db(librosa.feature.melspectrogram(S=S, sr=22050, n_mels=96, fmax=8000), ref=np.max)
    onset = librosa.onset.onset_strength(S=logmel, sr=22050, hop_length=HOP, lag=2, max_size=3)
    f0, vflag, _ = librosa.pyin(y, fmin=70, fmax=1000, sr=22050, frame_length=2048, hop_length=HOP, center=True)
    n = min(len(rms), len(f0), len(onset))
    return dict(hop_s=HOP / 22050, rms_db=librosa.amplitude_to_db(rms[:n], ref=1.0), onset=onset[:n], f0=f0[:n], voiced=vflag[:n])


def vocal_onsets(f):
    """Vocal note onsets: log-mel flux peaks plus legato pitch jumps > 0.8 semitone (original algorithm)."""
    hop = float(f["hop_s"]); on = f["onset"]; rms = f["rms_db"]
    loc = maximum_filter1d(rms, int(2.0 / hop))
    active = (rms > -45) & (rms > loc - 25)
    thr = uniform_filter1d(on, int(0.4 / hop)) * 1.5 + 0.15 * np.percentile(on, 99)
    pk, _ = find_peaks(on, height=0, distance=int(0.09 / hop))
    pk = [p for p in pk if on[p] > thr[p] and active[min(len(active) - 1, p + int(0.03 / hop))]]
    t_flux = np.array(pk) * hop
    s_flux = np.array([on[p] for p in pk]) if pk else np.array([1.0])
    midi = librosa.hz_to_midi(np.where(f["voiced"] > 0, f["f0"], np.nan))
    med = median_filter(np.nan_to_num(midi, nan=0), 9)
    w = int(0.04 / hop)
    jumps = [i for i in range(w, len(med) - w) if med[i - w] > 0 and med[i + w] > 0 and abs(med[i + w] - med[i - w]) > 0.8 and active[i]]
    t_pitch, last = [], -1e9
    for i in jumps:
        if i - last > int(0.1 / hop): t_pitch.append(i * hop)
        last = i
    ts = list(zip(t_flux, s_flux / (np.percentile(s_flux, 95) + 1e-9)))
    for t in t_pitch:
        if len(t_flux) == 0 or np.min(np.abs(t_flux - t)) > 0.08: ts.append((t, 0.35))
    ts.sort()
    return [(float(t), float(min(1.0, max(0.1, s)))) for t, s in ts]


def main():
    args = sys.argv[1:]
    proj = common.Project(args[0])
    bpm_hint = float(args[args.index("--bpm") + 1]) if "--bpm" in args else None
    k_sec = int(args[args.index("--sections") + 1]) if "--sections" in args else None
    mix = proj.load_mix(SR)
    duration = len(mix) / SR
    stems = {n: proj.load_stem(n, sr=SR)[: len(mix)] for n in ("vocals", "drums", "bass", "other")}
    for n in stems:
        if len(stems[n]) < len(mix): stems[n] = np.pad(stems[n], (0, len(mix) - len(stems[n])))

    bpm, P, off, kick_res = fit_grid(stems["drums"], mix, SR, duration, bpm_hint)
    print(f"tempo {bpm:.3f} BPM  period {P:.5f}s  first beat {off:.4f}s  kick residual sd {kick_res.std() * 1000 if len(kick_res) else float('nan'):.1f} ms ({len(kick_res)} kicks)")
    beats = off + P * np.arange(int((duration - off) / P) + 1)

    n = int(math.ceil(duration * FPS))
    env = {"rms": frame_rms(mix, SR)[:n]}
    for name, (lo, hi) in {"low": (None, 150), "mid": (150, 2000), "high": (4000, None)}.items():
        env[name] = frame_rms(sosfiltfilt(band_sos(lo, hi, SR), mix), SR)[:n]
    for s in ("vocal", "drums", "bass", "other"):
        env[s] = frame_rms(stems["vocals" if s == "vocal" else s], SR)[:n]
    for k in env:
        env[k] = [round(float(x), 3) for x in norm01(smooth_env(env[k]))]

    has_drums = np.abs(stems["drums"]).max() > 1e-3
    if has_drums:
        (kt, kdb), (st, sdb), (ht, hdb), _ = drum_onsets(stems["drums"], SR, P, off)
    else:
        kt = st = ht = kdb = sdb = hdb = np.array([])
    phase, ph_scores = bar_phase(beats, P, kt, st, mix, SR)
    downbeats = beats[phase::4]
    print(f"bar phase {phase} (scores per phase {ph_scores}; close scores = uncertain, check QA)")
    vf = vocal_feats(stems["vocals"], SR)
    onsets = {
        "kick": [[round(float(t), 3), round(float(s), 3)] for t, s in zip(kt, strength01(kdb))],
        "snare": [[round(float(t), 3), round(float(s), 3)] for t, s in zip(st, strength01(sdb))],
        "hat": [[round(float(t), 3), round(float(s), 3)] for t, s in zip(ht, strength01(hdb))],
        "vocal": [[round(t, 3), round(s, 3)] for t, s in vocal_onsets(vf)],
    }
    sections = find_sections(mix, SR, downbeats, duration, k_sec)
    doc = dict(duration=round(duration, 3), bpm=round(bpm, 3), beat_period=round(P, 5), time_signature=4,
               beats=[round(float(t), 3) for t in beats], downbeats=[round(float(t), 3) for t in downbeats],
               sections=sections, fps=FPS, **env, onsets=onsets,
               notes=f"generated by opus-video analyze_audio.py; bar phase scores {ph_scores}; sections are automatic (S01..), rename them by listening")
    (proj.data / "audio.json").write_text(json.dumps(doc, separators=(",", ":")))
    print("wrote", proj.data / "audio.json", f"{len(beats)} beats, {len(downbeats)} downbeats, {len(kt)} kicks, {len(st)} snares, {len(ht)} hats, {len(onsets['vocal'])} vocal onsets, {len(sections)} sections")
    for s in sections: print(f"  {s['name']} {s['start']:7.2f}-{s['end']:7.2f}  energy {s['energy']}")
    return doc


if __name__ == "__main__":
    main()
