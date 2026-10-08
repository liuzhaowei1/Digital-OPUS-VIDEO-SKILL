"""Grid-synthesized BGM for videos without a song: rhythm + pad + FX on the SAME beat grid as the picture.

Layers: drones + rhythm + edit-shaped FX, plus optional real-instrument voices (pad/bass/arp/motif/drums through Surge XT
or a GM SoundFont, see instruments.py). Everything is placed in BEATS from <proj>/cues.json, which the timeline
also reads, so cuts and sound cannot drift apart.

  python synth_bgm.py <proj> [--cues cues.json] [--out public/audio/bgm.wav] [--lufs -14] [--stems]

cues.json (all times in beats of the constant grid; beat 0 = beatOffset seconds):
{
  "bpm": 120, "beatOffset": 0, "duration": 15,          // duration in seconds
  "seed": 1, "key": "D",                                 // key only documents intent; chords drive the pad
  "sections": [ {"at": 0, "chord": "Dm", "drums": 0, "energy": 0.3},
                {"at": 4, "chord": "F",  "drums": 2, "energy": 0.8} ],
     // drums: 0 none | 1 kick | 2 kick + 16th ticks | 3 + offbeat open hats | 4 + clap on 2 & 4 (peak)
     // energy 0..1 (pad brightness/level)
  "cuts":    [4, 4.5, 6],          // visual cuts -> accent tick (the timeline cuts on the same numbers)
  "hits":    [24],                 // impacts (boom + noise burst + long reverb)
  "risers":  [[1, 4], [17, 20]],   // noise/pitch rise that lands exactly on the end beat
  "silence": [[23.5, 24]],         // everything gated out (use right before a hit)
  "tail": 24,                      // from here: no drums, pad decays to the end
  "voices": {                      // OPTIONAL. Without it the output is the original all-numpy synth, bit for bit
    "pad":   {"src": "surge:Pads/MKS-70 Warm Pad"},          // replaces the saw pad; 4-voice nearest-move voicing per chord
    "bass":  {"src": "surge:Basses/Sub 1"},                  // replaces the sub; root per beat (drums>=1), octave 8ths at drums 4
    "arp":   {"src": "gm:46", "from": 9, "rate": 0.25},      // chord tones cycling an octave up, until `until` (default tail)
    "motif": {"src": "surge:Plucks/Bell 1",                  // a short leitmotif stated at several beats, transposed
              "notes": [[0, "A4", 0.9], [1, "D5", 0.9], [2, "E5", 0.9], [3, "F5", 3]],   // [beat offset, note, length beats]
              "at": [[1, 0], [25, -2]], "final": {"at": 34, "notes": [[0, "A4", 1], [1, "D5", 6]]}},
    "kick":  {"src": "gm:drums"}, "snare": {"src": "gm:drums"}, "hats": {"src": "gm:drums"}   // replace the numpy drums
  },  // every voice also takes "gain" (default 1), "fx": false (skip its default FX chain), "note" (drum note override)
  "events": [     // OPTIONAL, times in SECONDS = picture time (the second clock): sounds that follow what the picture does
    {"type": "note", "t": 3.2, "src": "gm:47", "notes": ["D2"], "vel": 105, "dur": 1.4, "strum": 0},  // any instrument hit
    {"type": "glint", "t": 0.02}, {"type": "thud", "t0": 1.95, "t1": 2.4}, {"type": "roll", "t0": 3.0, "t1": 4.1},
    {"type": "swell", "t0": 6.3, "t1": 7.5},          // reverse-cymbal inhale INTO a hit: use instead of "silence" with voices
    {"type": "glide", "pts": [[4.1, "D5"], [5.5, 62.2]], "pan": [[4.1, 0.5]]},   // pitch line following a drawn curve
    {"type": "whine", "pts": [[7.5, 0], [12.4, 1]]},  // electric motor, pts = speed 0..1 (export it from the scene's formula)
    {"type": "rewind", "t0": 16.0, "t1": 16.875}, {"type": "shimmer", "t0": 17.15, "t1": 18.5, "notes": ["D6", "A6"]}
  ],              // every event takes "gain"; sounds are in sfx.py and all decay on their own (no hard stops)
  "cutAccent": 0.5,   // optional multiplier on the cut ticks
  // sections may also take "mute": ["kick", "arp", ...] (voice names) and "bass": "drone" | "pulse" | "off";
  // voices may take "role" (lets two voices share a role, e.g. "brass": {"role": "motif", ...}) and
  // "cutoff": [[t_sec, hz], ...] (lowpass automation, e.g. an arp opening up during a build)
  "pump": 0.15   // voices only: kick sidechain depth (numpy synth uses 0.55). With voices, silence = a -18 dB breath (not a mute),
                 // bass is legato, pad ties common tones, impacts decay fully, the end fades over 1.2 s
}
Writes the wav and updates public/project.json (bpm, beatOffset, duration, audio) so the engine's synthetic
grid = the music's grid. --stems also writes each layer to .analysis/bgm_stems/ for balancing.
"""
import argparse, json, re, subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
        "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def note_midi(name):
    """'A4' -> 69, 'Bb3' -> 58; ints pass through."""
    if isinstance(name, (int, float)):
        return int(name)
    m = re.fullmatch(r"([A-G][#b]?)(-?\d)", name)
    if not m:
        raise ValueError(f"note not understood: {name}")
    return NOTE[m.group(1)] + 12 * (int(m.group(2)) + 1)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def chord_notes(name):
    m = re.fullmatch(r"([A-G][#b]?)(m|maj7|m7|sus2|sus4|7)?", name)
    if not m:
        raise ValueError(f"chord not understood: {name}")
    root = NOTE[m.group(1)]
    iv = {None: [0, 4, 7], "m": [0, 3, 7], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10],
          "sus2": [0, 2, 7], "sus4": [0, 5, 7], "7": [0, 4, 7, 10]}[m.group(2)]
    base = 48 + root if root <= 7 else 36 + root          # keep the pad root around C3..G3
    return base, iv


def bp(lo, hi, order=2):
    return butter(order, [lo, hi], btype="band", fs=SR, output="sos")


def lp(f, order=2):
    return butter(order, f, btype="low", fs=SR, output="sos")


def hp(f, order=2):
    return butter(order, f, btype="high", fs=SR, output="sos")


class Synth:
    def __init__(self, cues):
        self.c = cues
        self.bpm = float(cues["bpm"])
        self.per = 60.0 / self.bpm
        self.off = float(cues.get("beatOffset", 0))
        self.dur = float(cues["duration"])
        self.n = int(round(self.dur * SR))
        self.rng = np.random.default_rng(cues.get("seed", 1))
        self.secs = sorted(cues["sections"], key=lambda s: s["at"])
        self.tail = cues.get("tail")
        self.silence = [tuple(map(self.t, s)) for s in cues.get("silence", [])]
        self.kicks = []
        self.voiced = bool(cues.get("voices"))               # real instruments: legato/continuity rules below

    def t(self, beat):
        return self.off + beat * self.per

    def sec_at(self, beat):
        cur = self.secs[0]
        for s in self.secs:
            if s["at"] <= beat + 1e-9:
                cur = s
        return cur

    def silent(self, t):
        return any(a - 1e-4 <= t < b for a, b in self.silence)

    def place(self, buf, t, x, gain=1.0):
        i = int(round(t * SR))
        if i >= self.n or i + len(x) <= 0:
            return
        a, b = max(i, 0), min(i + len(x), self.n)
        buf[a:b] += gain * x[a - i:b - i]

    # ---- instruments -------------------------------------------------------------------------------
    def kick(self):
        L = int(0.55 * SR); tt = np.arange(L) / SR
        f = 46 + 150 * np.exp(-tt / 0.035)                    # pitch drop 196 -> 46 Hz (the "whomp")
        ph = 2 * np.pi * np.cumsum(f) / SR
        body = np.sin(ph) * np.exp(-tt / 0.28)
        click = sosfilt(hp(1500), self.rng.standard_normal(L)) * np.exp(-tt / 0.004) * 0.35
        x = np.tanh(1.6 * (body + click)) / np.tanh(1.6)
        return x

    def tick(self, bright=1.0, L=0.05):
        L = int(L * SR); tt = np.arange(L) / SR
        return sosfilt(hp(6500 + 2500 * bright), self.rng.standard_normal(L)) * np.exp(-tt / 0.012)

    def tock(self):                                           # cut accent: short mid click + air
        L = int(0.09 * SR); tt = np.arange(L) / SR
        mid = sosfilt(bp(1400, 3200), self.rng.standard_normal(L)) * np.exp(-tt / 0.018)
        ping = np.sin(2 * np.pi * 2600 * tt) * np.exp(-tt / 0.01) * 0.3
        return mid * 0.8 + ping + self.tick(1.0, 0.09) * 0.5

    def ohat(self):
        L = int(0.25 * SR); tt = np.arange(L) / SR
        return sosfilt(hp(7000), self.rng.standard_normal(L)) * np.exp(-tt / 0.07)

    def clap(self):                                           # 3 quick noise bursts + short tail: backbeat for peaks
        L = int(0.3 * SR); tt = np.arange(L) / SR
        env = np.zeros(L)
        for d in (0.0, 0.011, 0.022):
            i = int(d * SR); env[i:] = np.maximum(env[i:], np.exp(-(tt[: L - i]) / (0.008 if d < 0.02 else 0.09)))
        return sosfilt(bp(900, 5000), self.rng.standard_normal(L)) * env

    def impact(self):
        L = int(5.0 * SR); tt = np.arange(L) / SR            # was 3.0 s: stopped at -27 dB re peak (a cut), fixed 2026-10-02
        f = 32 + 60 * np.exp(-tt / 0.12)
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.9)
        burst = sosfilt(lp(3500), self.rng.standard_normal(L)) * np.exp(-tt / 0.18)
        x = np.tanh(1.3 * (boom + 0.55 * burst))
        x[-int(0.5 * SR):] *= np.linspace(1, 0, int(0.5 * SR)) ** 2   # reach zero before the buffer ends
        return x

    def riser(self, t0, t1):
        L = int((t1 - t0) * SR); tt = np.arange(L) / SR; u = tt / max(t1 - t0, 1e-3)
        amp = u ** 2.6
        noise = self.rng.standard_normal(L)
        # a rising band: blend four fixed bands as the sweep moves up (cheap time-varying filter)
        bands = [(300, 900), (900, 2500), (2500, 6000), (6000, 14000)]
        w = np.stack([np.clip(1 - abs(u * 3 - k), 0, 1) for k in range(4)])
        swept = sum(w[k] * sosfilt(bp(*bands[k]), noise) for k in range(4))
        f = 180 * (8 ** u)                                    # 180 -> 1440 Hz pitched sweep under the noise
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
        x = (swept * 1.4 + tone) * amp
        x[-int(0.004 * SR):] *= np.linspace(1, 0, int(0.004 * SR))   # hard stop exactly on the target beat
        return x

    def pad_section(self, s, t0, t1, rel):
        """Detuned band-limited saws on the chord, lowpassed by energy; fades so sections overlap smoothly."""
        base, iv = chord_notes(s["chord"])
        e = float(s.get("energy", 0.5))
        a, b = max(t0 - 0.12, 0), min(t1 + rel, self.dur)
        L = int((b - a) * SR); tt = np.arange(L) / SR
        out = np.zeros((2, L))
        notes = [base + i for i in iv] + [base + 12]
        for k, m in enumerate(notes):
            for d, pan in ((-9, 0.2), (0, 0.5), (9, 0.8)):  # cents detune, stereo spread
                f0 = hz(m) * 2 ** (d / 1200)
                ph0 = self.rng.uniform(0, 2 * np.pi)
                v = np.zeros(L)
                for h in range(1, int(min(24, 9000 / f0)) + 1):   # band-limited saw
                    v += np.sin(2 * np.pi * f0 * h * tt + ph0 * h) / h
                out[0] += v * (1 - pan); out[1] += v * pan
        out *= 1 / (len(notes) * 3)
        cut = 500 + 2600 * e
        out = sosfilt(lp(cut, 2), out, axis=1)
        env = np.ones(L)
        fi = int(min(0.12, (t0 - a) + 0.12) * SR)
        env[:fi] = np.linspace(0, 1, fi) if fi else env[:fi]
        fo = int(min(rel, b - t1 + 1e-3) * SR)
        if fo > 0:
            env[-fo:] *= np.exp(-np.linspace(0, 5, fo))
        return a, out * env * (0.35 + 0.65 * e)

    def sub_section(self, s, t0, t1):
        base, _ = chord_notes(s["chord"])
        a, b = t0, min(t1 + 0.05, self.dur)
        L = int((b - a) * SR); tt = np.arange(L) / SR
        x = np.sin(2 * np.pi * hz(base - 12) * tt) * 0.8 + np.sin(2 * np.pi * hz(base) * tt) * 0.12
        ramp = int(0.03 * SR); x[:ramp] *= np.linspace(0, 1, ramp); x[-ramp:] *= np.linspace(1, 0, ramp)
        return a, x

    def reverb(self, x, seconds=2.2, decay=0.55, wet=0.2):
        L = int(seconds * SR); tt = np.arange(L) / SR
        ir = np.stack([self.rng.standard_normal(L), self.rng.standard_normal(L)]) * np.exp(-tt / decay)
        ir = sosfilt(lp(6000), ir, axis=1); ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
        y = np.stack([fftconvolve(x[c], ir[c])[: x.shape[1]] for c in range(2)])
        return x + wet * y

    # ---- real-instrument voices (cues["voices"]) and picture-timed events (cues["events"]) ---------------
    BUILTIN_STEM = {"pad": "pad", "bass": "sub", "kick": "kick", "snare": "clap", "hats": "ticks"}   # voices that replace a numpy layer
    ROLES = ("pad", "bass", "kick", "snare", "hats", "arp", "motif")
    VOICE_PEAK = {"pad": 0.5, "bass": 0.55, "arp": 0.3, "motif": 0.35, "kick": 0.9, "snare": 0.45, "hats": 0.3}
    GM_DRUM = {"kick": 36, "snare": 38, "hats": 42}

    def gated(self, t):
        return any(a - 1e-4 <= t < b for a, b in self.silence)

    def voicing(self, chord, prev, lo=50, hi=74):
        import itertools
        base, iv = chord_notes(chord)
        pcs = {(base + i) % 12 for i in iv}
        cand = [m for m in range(lo, hi + 1) if m % 12 in pcs]
        opts = [v for v in itertools.combinations(cand, 4) if {m % 12 for m in v} >= pcs and v[-1] - v[0] <= 17]
        if prev is None:
            return min(opts, key=lambda v: abs(np.mean(v) - (lo + hi) / 2))
        return min(opts, key=lambda v: sum(abs(a - b) for a, b in zip(v, prev)) + 0.3 * abs(np.mean(v) - (lo + hi) / 2))

    def muted(self, name, beat):
        return name in self.sec_at(beat).get("mute", [])

    def voice_notes(self, name, role, cfg, drums_end):
        """Score one voice as [(t_sec, midi, vel, dur_sec)] from the same sections/cuts the picture uses."""
        notes, prev = [], None
        cuts = set(self.c.get("cuts", []))
        jit = lambda b: 0.0 if b in cuts else self.rng.normal(0, 0.002)  # noqa: E731  cut beats stay exact
        end_beat = (self.dur - self.off) / self.per
        if role in ("kick", "snare", "hats"):
            note = cfg.get("note", self.GM_DRUM[role] if cfg["src"] == "gm:drums" else 60)
            for i in range(int(np.ceil(drums_end * 4))):
                b = i / 4; t = self.t(b); s = self.sec_at(b); dr = s.get("drums", 0); e = s.get("energy", 0.5)
                if self.gated(t) or self.muted(name, b):
                    continue
                if role == "kick" and dr >= 1 and i % 4 == 0:
                    notes.append((t, note, 100 + 20 * e, 0.2))
                if role == "snare" and dr >= 4 and i % 8 == 4:
                    notes.append((t, note, 105, 0.2))
                if role == "hats" and dr >= 2:
                    v = [90, 45, 70, 50][i % 4] * (0.6 + 0.4 * e) + self.rng.normal(0, 5)
                    notes.append((t + jit(b), note, v, 0.05))
                    if dr >= 3 and i % 4 == 2 and cfg["src"] == "gm:drums":
                        notes.append((t, 46, 60, 0.2))
            return notes
        if role == "motif":
            phrase = [(o, note_midi(n), ln) for o, n, ln in cfg["notes"]]
            for at, tr in cfg.get("at", []):
                for o, m, ln in phrase:
                    t = self.t(at + o)
                    if not self.gated(t):
                        notes.append((t, m + tr, cfg.get("vel", 85), ln * self.per))
            if "final" in cfg:
                for o, n, ln in cfg["final"]["notes"]:
                    notes.append((self.t(cfg["final"]["at"] + o), note_midi(n), cfg.get("vel", 85) + 5, ln * self.per))
            return notes
        for j, s in enumerate(self.secs):
            b0 = s["at"]; b1 = self.secs[j + 1]["at"] if j + 1 < len(self.secs) else end_beat
            e = s.get("energy", 0.5); dr = s.get("drums", 0)
            v = prev = self.voicing(s["chord"], prev, *cfg.get("range", (50, 74)))
            if self.muted(name, b0):
                continue
            if role == "pad":                                # common tones are tied over the change, not re-attacked
                held = {n[1]: k for k, n in enumerate(notes) if abs(n[0] + n[3] - 0.1 - self.t(b0)) < 0.05}
                for m in v:
                    if m in held:
                        t0, mm, vel, d = notes[held[m]]; notes[held[m]] = (t0, mm, vel, d + (b1 - b0) * self.per)
                    else:
                        notes.append((self.t(b0) - 0.02, m, 50 + 40 * e, (b1 - b0) * self.per + 0.1))
            elif role == "bass":
                root = 36 + (chord_notes(s["chord"])[0] - 36) % 12      # C2..B2
                mode = s.get("bass", "pulse" if dr >= 1 and b0 < drums_end else "off")
                if mode == "drone":
                    notes.append((self.t(b0), root, 80 + 20 * e, (b1 - b0) * self.per + 0.05))
                elif mode == "pulse":
                    step = 0.5 if dr >= 4 else 1.0
                    b = b0
                    while b < min(b1, drums_end) - 1e-9:
                        up = step == 0.5 and round(b * 2) % 2 == 1
                        if not self.gated(self.t(b)):
                            notes.append((self.t(b), root + 12 * up, 70 if up else 95, step * self.per * 1.02))   # legato
                        b += step
            elif role == "arp":
                lo_b, hi_b = cfg.get("from", 0), cfg.get("until", drums_end)
                rate = cfg.get("rate", 0.25)
                seq = [m + 12 for m in v] + [v[1] + 24, v[2] + 24]
                b, k = max(b0, lo_b), 0
                while b < min(b1, hi_b) - 1e-9:
                    if not self.gated(self.t(b)):
                        acc = [1.0, 0.55, 0.75, 0.6][round(b * 4) % 4]
                        notes.append((self.t(b) + jit(b), seq[k % len(seq)], (40 + 60 * e) * acc + self.rng.normal(0, 5),
                                      rate * self.per * 0.8))
                    b += rate; k += 2 if k % 7 == 3 else 1                # skip a step now and then: no fixed loop
        return notes

    def _automate_lp(self, x, pts):
        """Time-varying lowpass: cutoff follows pts [[t_sec, hz], ...] (log-interpolated), 512-sample blocks."""
        from pedalboard import LowpassFilter
        p = np.asarray(pts, float); f = LowpassFilter(cutoff_frequency_hz=float(p[0, 1]))
        y = np.zeros_like(x, dtype=np.float32); B = 512
        for i in range(0, x.shape[1], B):
            f.cutoff_frequency_hz = float(np.exp(np.interp(i / SR, p[:, 0], np.log(p[:, 1]))))
            y[:, i:i + B] = f(x[:, i:i + B].astype(np.float32), SR, reset=False)
        return y.astype(np.float64)

    def apply_voices(self, st, drums_end):
        import instruments
        from pedalboard import Pedalboard, Reverb, Delay, HighpassFilter, LowpassFilter, Chorus
        fx = {"pad": [HighpassFilter(180), Chorus(rate_hz=0.3, depth=0.15, mix=0.3),
                      Reverb(room_size=0.85, wet_level=0.35, dry_level=0.7)],
              "arp": [HighpassFilter(300), Delay(delay_seconds=0.75 * self.per, feedback=0.35, mix=0.25),
                      Reverb(room_size=0.6, wet_level=0.2, dry_level=0.85)],
              "motif": [Delay(delay_seconds=1.5 * self.per, feedback=0.4, mix=0.3),
                        Reverb(room_size=0.9, wet_level=0.4, dry_level=0.75)],
              "bass": [LowpassFilter(900)]}
        self.extra = []
        for name, cfg in self.c["voices"].items():
            role = cfg.get("role", name)
            if role not in self.ROLES:
                raise ValueError(f"voice {name}: unknown role {role} (one of {self.ROLES}; other names need \"role\")")
            notes = self.voice_notes(name, role, cfg, drums_end)
            if role == "kick":                               # the pump follows the kicks actually played (mutes included)
                self.kicks = [n[0] for n in notes]
            x = instruments.render(cfg["src"], notes, self.dur) if notes else np.zeros((2, self.n))
            if "cutoff" in cfg:
                x = self._automate_lp(x, cfg["cutoff"])
            if role in fx and cfg.get("fx", True):
                x = Pedalboard(fx[role])(x.astype(np.float32), SR).astype(np.float64)
            pk = np.abs(x).max()
            x = x / pk * self.VOICE_PEAK[role] * cfg.get("gain", 1.0) if pk > 0 else x
            stem = self.BUILTIN_STEM.get(name) if name == role else None
            if stem is None:
                stem = name; self.extra.append(name)
            st[stem] = x
            print(f"  voice {name:6s} {cfg['src']:34s} {len(notes):4d} notes", flush=True)

    def render_events(self):
        """cues["events"] (times in SECONDS, i.e. picture time): "note" events go through instruments.py grouped by
        src; every other type is a sync sound from sfx.py. Returns the (2, n) stem."""
        import instruments, sfx
        from pedalboard import Pedalboard, Reverb
        out = np.zeros((2, self.n)); by_src = {}
        for ev in self.c["events"]:
            ty, g = ev["type"], ev.get("gain", 1.0)
            if ty == "note":
                for k, nm in enumerate(ev["notes"]):
                    by_src.setdefault(ev["src"], []).append(
                        (ev["t"] + k * ev.get("strum", 0), note_midi(nm), ev.get("vel", 100), ev.get("dur", 1.0), g))
                continue
            t0 = ev.get("t", ev.get("t0", ev["pts"][0][0] if "pts" in ev else 0))
            if ty == "glint":
                x = sfx.glint(self.rng)
            elif ty in ("thud", "roll", "swell", "rewind"):
                x = getattr(sfx, ty)(self.rng, ev["t0"], ev["t1"])
            elif ty == "glide":
                x = sfx.glide(self.rng, [[t, note_midi(m)] for t, m in ev["pts"]], ev.get("pan"))
            elif ty == "whine":
                x = sfx.whine(self.rng, ev["pts"])
            elif ty == "shimmer":
                x = sfx.shimmer(self.rng, ev["t0"], ev["t1"], [note_midi(m) for m in ev["notes"]])
            else:
                raise ValueError(f"unknown event type {ty}")
            for c in range(2):
                self.place(out[c], t0, x[c], g)
        for src, ns in by_src.items():
            for gain in sorted({n[4] for n in ns}):
                part = [n[:4] for n in ns if n[4] == gain]
                out += instruments.render(src, part, self.dur) * gain * 0.6
            print(f"  events {src:33s} {len(ns):4d} notes", flush=True)
        out = Pedalboard([Reverb(room_size=0.7, wet_level=0.25, dry_level=0.9)])(out.astype(np.float32), SR).astype(np.float64)
        print(f"  events total {len(self.c['events'])}", flush=True)
        return out

    # ---- arrangement -------------------------------------------------------------------------------
    def render(self):
        n = self.n
        st = {k: np.zeros((2, n)) for k in ("kick", "ticks", "clap", "cuts", "pad", "sub", "fx")}
        mono = lambda k: st[k]  # noqa: E731
        end_beat = (self.dur - self.off) / self.per
        drums_end = self.tail if self.tail is not None else end_beat

        # drums on the 16th grid
        k, ti = self.kick(), self.tick()
        for i in range(int(np.ceil(end_beat * 4))):
            beat = i / 4
            if beat >= drums_end:
                break
            t = self.t(beat); s = self.sec_at(beat); dr = s.get("drums", 0); e = s.get("energy", 0.5)
            if self.silent(t):
                continue
            if dr >= 1 and i % 4 == 0:
                for c in range(2):
                    self.place(st["kick"][c], t, k, 0.9 * (0.7 + 0.3 * e))
                self.kicks.append(t)
            if dr >= 2:
                vel = [0.55, 0.22, 0.4, 0.25][i % 4] * (0.6 + 0.4 * e)
                pan = 0.35 if i % 2 else 0.65
                self.place(st["ticks"][0], t, ti, vel * (1 - pan)); self.place(st["ticks"][1], t, ti, vel * pan)
            if dr >= 3 and i % 4 == 2:
                oh = self.ohat()
                for c in range(2):
                    self.place(st["ticks"][c], t, oh, 0.25)
            if dr >= 4 and i % 8 == 4:                        # beats 2 and 4 of the bar
                cl = self.clap()
                for c in range(2):
                    self.place(st["clap"][c], t, cl, 0.8)

        # cut accents: the picture cuts exactly here, so the ear gets a transient exactly here
        for cb in self.c.get("cuts", []):
            t = self.t(cb)
            if self.silent(t) or t >= self.dur:
                continue
            x = self.tock(); pan = 0.5 + 0.25 * np.sin(cb * 2.3)
            self.place(st["cuts"][0], t, x, 0.55 * (1 - pan) * 2); self.place(st["cuts"][1], t, x, 0.55 * pan * 2)

        # pad + sub per section (tail section releases slowly to the end)
        for j, s in enumerate(self.secs):
            t0 = self.t(s["at"])
            t1 = self.t(self.secs[j + 1]["at"]) if j + 1 < len(self.secs) else self.dur
            rel = 0.35 if j + 1 < len(self.secs) else 0.05
            a, x = self.pad_section(s, t0, t1, rel)
            i = int(round(a * SR)); m = min(x.shape[1], n - i)
            st["pad"][:, i:i + m] += x[:, :m]
            if s.get("drums", 0) >= 1:
                a, x = self.sub_section(s, t0, min(t1, self.t(drums_end)))
                i = int(round(a * SR)); m = min(len(x), n - i)
                st["sub"][:, i:i + m] += x[:m] * 0.45

        self.extra = []
        if self.c.get("voices"):
            self.apply_voices(st, drums_end)

        # sidechain: pad and sub duck on every kick (the "pump")
        duck = np.ones(n); tt = np.arange(int(0.3 * SR)) / SR; shape = 1 - (self.c.get("pump", 0.15) if self.voiced else 0.55) * np.exp(-tt / 0.09)
        for kt in self.kicks:
            i = int(round(kt * SR)); m = min(len(shape), n - i)
            duck[i:i + m] = np.minimum(duck[i:i + m], shape[:m])
        st["pad"] *= duck; st["sub"] *= duck
        for k in self.extra:
            if self.c["voices"][k].get("role", k) in ("arp", "pad", "bass"):
                st[k] *= duck

        # tail: pad decays from the tail beat to the end
        if self.tail is not None:
            i = int(round(self.t(self.tail) * SR))
            L = n - i
            if L > 0:
                st["pad"][:, i:] *= np.exp(-np.linspace(0, 3.2, L))

        # FX
        for r0, r1 in self.c.get("risers", []):
            x = self.riser(self.t(r0), self.t(r1))
            for c, g in ((0, 0.9), (1, 1.0)):
                self.place(st["fx"][c], self.t(r0), x, 0.5 * g)
        hits = [self.t(h) for h in self.c.get("hits", [])]

        if "cutAccent" in self.c:
            st["cuts"] *= float(self.c["cutAccent"])
        mix = (st["kick"] * 1.0 + st["ticks"] * 0.5 + st["clap"] * 0.55 + st["cuts"] * 0.6 + st["pad"] * 0.9 + st["sub"] * 1.0
               + st["fx"] * 0.7)
        for k in self.extra:
            mix = mix + st[k]
        mix = self.reverb(mix, wet=0.14)
        # silence gates the whole mix (reverb tails included), then impacts land on top
        g = np.ones(n); ramp = int(0.008 * SR)
        for a, b in self.silence:
            i, j = int(a * SR), int(b * SR)
            if self.voiced:                                  # a breath, not a mute: sustains/reverb sink to -18 dB
                floor, r = 10 ** (-18 / 20), int(0.09 * SR)  # over 90 ms (raised cosine) and rise in 15 ms
                k0 = max(i - r, 0); w = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, i - k0))
                g[k0:i] = np.minimum(g[k0:i], floor + (1 - floor) * w); g[i:j] = floor
                u = int(0.015 * SR); g[max(j - u, i):j] = np.linspace(floor, 1, j - max(j - u, i))
                continue
            g[i:j] = 0; g[max(i - ramp, 0):i] = np.linspace(1, 0, i - max(i - ramp, 0))
        mix *= g
        imp = np.zeros((2, n))
        for h in hits:
            x = self.impact()
            for c in range(2):
                self.place(imp[c], h, x, 0.8)
        mix += self.reverb(imp, seconds=3.5, decay=1.1, wet=0.35)
        st["impact"] = imp
        if self.c.get("events"):                             # picture-timed sync sounds: after the gate, never ducked
            st["sync"] = self.render_events(); mix += st["sync"]
        fade = int((1.2 if self.voiced else 0.04) * SR)
        mix[:, -fade:] *= np.linspace(1, 0, fade) ** (2 if self.voiced else 1)
        return mix, st


def ebur128(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    summ = r[r.rfind("Summary:"):]
    I = float(re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summ).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summ).group(1))
    return I, tp


def write(path, x):
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(path), SR, np.clip(x.T, -1, 1).astype(np.float32))


def master(mix, out, target, ceiling=-1.0):
    """Normalize to target LUFS with a soft limiter so true peak stays under the ceiling (2 passes)."""
    x = mix / max(np.abs(mix).max(), 1e-9) * 0.5
    for _ in range(3):
        write(out, x)
        I, tp = ebur128(out)
        x = x * 10 ** ((target - I) / 20)
        c = 10 ** ((ceiling - 0.6) / 20)
        x = c * np.tanh(x / c)                                 # soft limiter: transparent below ~-3 dBFS
    write(out, x)
    I, tp = ebur128(out)
    for _ in range(4):                                         # inter-sample peaks can still exceed the ceiling
        if tp <= ceiling - 0.1:                                # (bright transients); trade a little loudness for it
            break
        x = x * 10 ** ((ceiling - 0.3 - tp) / 20)
        write(out, x)
        I, tp = ebur128(out)
    return I, tp


def main():
    import common  # noqa: F401  (sets caches)
    ap = argparse.ArgumentParser()
    ap.add_argument("proj")
    ap.add_argument("--cues", default="cues.json")
    ap.add_argument("--out", default="public/audio/bgm.wav")
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--stems", action="store_true")
    a = ap.parse_args()
    proj = Path(a.proj).resolve()
    cues = json.loads((proj / a.cues).read_text())
    syn = Synth(cues)
    mix, st = syn.render()
    out = proj / a.out
    I, tp = master(mix, out, a.lufs)
    if a.stems:
        for k, v in st.items():
            write(proj / ".analysis" / "bgm_stems" / f"{k}.wav", v / max(np.abs(v).max(), 1e-9) * 0.8)
    pj = proj / "public" / "project.json"
    p = json.loads(pj.read_text()) if pj.exists() else {}
    p.update(bpm=syn.bpm, beatOffset=syn.off, duration=syn.dur, audio=str(out.relative_to(proj / "public")))
    pj.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n")
    print(f"{out}  {syn.dur:.2f}s  {syn.bpm:g} BPM  I={I:.1f} LUFS  TP={tp:.1f} dBFS  kicks={len(syn.kicks)} "
          f"cuts={len(cues.get('cuts', []))}; project.json synced (bpm/beatOffset/duration/audio)")


if __name__ == "__main__":
    main()
