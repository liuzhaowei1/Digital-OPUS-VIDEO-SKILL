"""Real instruments for synth_bgm.py: render a note list through Surge XT (VST3 via pedalboard) or a GM SoundFont
(fluidsynth CLI). Both return float64 (2, n) at 44.1 kHz with notes sample-accurate (<1 ms, measured).

  src = "surge:Pads/MKS-70 Warm Pad"   factory patch path under patches_factory/ (".fxp" optional)
  src = "gm:48"                        General MIDI program 0-127 (48 = strings ensemble, 0 = piano, 46 = harp)
  src = "gm:drums"                     GM drum kit (channel 10); note numbers pick the drum (36 kick, 38 snare, 42 hat…)
notes = [(t_sec, midi, velocity 1-127, dur_sec), ...]

Surge renders are NOT bit-reproducible run to run (random oscillator phase); render once and keep the wav.
"""
import os, struct, subprocess, tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 44100
SURGE = Path(os.environ.get("SURGE_XT", Path(os.environ.get("OPUS_HOME", Path.home() / "opus-video")) / "_plugins/surge-xt"))
SURGE_VST3 = SURGE / "lib/vst3/Surge XT.vst3"
SURGE_PATCHES = SURGE / "share/surge-xt/patches_factory"
SF2 = Path(os.environ.get("GM_SF2", "/usr/share/sounds/sf2/FluidR3_GM.sf2"))

_A = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"


def _juce_b64(b):
    """JUCE MemoryBlock::toBase64Encoding (custom alphabet, little-endian 6-bit groups, '<size>.' prefix)."""
    bits = np.unpackbits(np.frombuffer(b, np.uint8), bitorder="little")
    bits = np.concatenate([bits, np.zeros((-len(bits)) % 6, np.uint8)]).reshape(-1, 6)
    vals = (bits * (1 << np.arange(6))).sum(1)
    return f"{len(b)}." + "".join(_A[v] for v in vals)


def surge_patches():
    return sorted(str(p.relative_to(SURGE_PATCHES))[:-4] for p in SURGE_PATCHES.rglob("*.fxp"))


def _surge(patch):
    from pedalboard import load_plugin
    if not SURGE_VST3.exists():
        raise FileNotFoundError(f"Surge XT not found at {SURGE} (see docs/SETUP.md)")
    f = SURGE_PATCHES / (patch if patch.endswith(".fxp") else patch + ".fxp")
    if not f.exists():
        raise FileNotFoundError(f"Surge patch not found: {f.relative_to(SURGE_PATCHES)} (list: instruments.surge_patches())")
    p = load_plugin(str(SURGE_VST3))
    b = f.read_bytes(); b = b[b.find(b"sub3"):]          # .fxp = 56-byte FXP header + Surge's own state chunk
    xml = ('<?xml version="1.0" encoding="UTF-8"?> <VST3PluginState><IComponent>' + _juce_b64(b)
           + '</IComponent></VST3PluginState> ').encode()
    p.raw_state = b"VC2!" + struct.pack("<I", len(xml)) + xml
    p([], duration=0.3, sample_rate=SR, num_channels=2, reset=False)   # state is applied on the first block: warm up
    return p


def _fit(a, n):
    out = np.zeros((2, n)); m = min(n, a.shape[1]); out[:, :m] = a[:, :m]
    return out


def render_surge(patch, notes, dur):
    from mido import Message
    msgs = []
    for t, m, v, d in notes:
        msgs += [Message("note_on", note=int(m), velocity=int(np.clip(v, 1, 127)), time=max(float(t), 0.0)),
                 Message("note_off", note=int(m), time=min(float(t + d), dur - 0.005))]
    msgs.sort(key=lambda x: x.time)                       # pedalboard reads msg.time as absolute seconds
    a = _surge(patch)(msgs, duration=dur, sample_rate=SR, num_channels=2, reset=False)
    return _fit(a.astype(np.float64), int(round(dur * SR)))


def render_gm(program, notes, dur):
    import mido
    from scipy.io import wavfile
    if not SF2.exists():
        raise FileNotFoundError(f"SoundFont not found: {SF2} (sudo apt install fluidsynth fluid-soundfont-gm)")
    drums = program == "drums"
    ch = 9 if drums else 0
    tpb, tempo = 960, 500000                             # 120 BPM ticks: 1 tick = 1/1920 s, quantization 0.52 ms
    ev = []
    for t, m, v, d in notes:
        ev.append((max(float(t), 0.0), 1, mido.Message("note_on", channel=ch, note=int(m), velocity=int(np.clip(v, 1, 127)))))
        ev.append((min(float(t + d), dur - 0.005), 0, mido.Message("note_off", channel=ch, note=int(m))))
    ev.sort(key=lambda e: (e[0], e[1]))
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=tempo))
    if not drums:
        tr.append(mido.Message("program_change", channel=ch, program=int(program)))
    last = 0
    for t, _, msg in ev:
        tick = int(round(t * 1e6 / tempo * tpb)); msg.time = tick - last; last = tick; tr.append(msg)
    with tempfile.TemporaryDirectory() as td:
        mid, wav = Path(td) / "x.mid", Path(td) / "x.wav"
        mf = mido.MidiFile(ticks_per_beat=tpb); mf.tracks.append(tr); mf.save(mid)
        # -R 0 -C 0: no built-in reverb/chorus (FX are applied in synth_bgm); -g 0.5 keeps headroom
        subprocess.run(["fluidsynth", "-ni", "-R", "0", "-C", "0", "-g", "0.5", "-r", str(SR), "-F", str(wav),
                        str(SF2), str(mid)], check=True, capture_output=True)
        sr, a = wavfile.read(wav)
    a = a.astype(np.float64) / (32768.0 if a.dtype == np.int16 else 1.0)
    return _fit(a.T, int(round(dur * SR)))


def _no_self_overlap(notes):
    """A note_off that lands after the next note_on of the SAME pitch kills the new note (legato repeats): clip it."""
    out, nxt = [], {}
    for t, m, v, d in sorted(notes, key=lambda x: -x[0]):
        if m in nxt:
            d = min(d, nxt[m] - t - 0.002)
        nxt[m] = t
        out.append((t, m, v, max(d, 0.01)))
    return out[::-1]


def render(src, notes, dur):
    notes = _no_self_overlap(notes)
    kind, _, arg = src.partition(":")
    if kind == "surge":
        return render_surge(arg, notes, dur)
    if kind == "gm":
        return render_gm(arg if arg == "drums" else int(arg), notes, dur)
    raise ValueError(f"unknown instrument source: {src} (surge:<patch> | gm:<program> | gm:drums)")
