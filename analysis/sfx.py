"""Sync sounds for synth_bgm.py `events`: sounds that follow what the PICTURE does at its own times (seconds, not beats).

Every function returns float64 (2, L) starting at its onset, and every sound ends in its own decay or fade
(no buffer ever stops while still sounding). `rng` is a numpy Generator so renders stay reproducible.

  glint(rng)                      tiny glassy sparkle (a light point appears)
  thud(rng, t0, t1)               reverse swell sucked in from t0, landing as a soft low thud at t1
  roll(rng, t0, t1)               mechanical clicks accelerating t0 -> t1 (a number reel spinning up), ends on a catch
  swell(rng, t0, t1)              reverse-cymbal inhale that peaks exactly at t1 (replaces hard silence before a hit)
  glide(rng, pts, pan=None)       soft sine line whose pitch follows pts [[t, midi], ...] (a drawn curve); pan [[t, -1..1]]
  whine(rng, pts)                 electric-motor whine; pts [[t, speed 0..1]] -> pitch/brightness/level
  rewind(rng, t0, t1)             tape-rewind chatter: warbling high squeal + spool whirr, slowing into a clunk at t1
  shimmer(rng, t0, t1, notes)     a chain of sparkles running across t0..t1 on the given pitches
"""
import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100


def _sos(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


def _hz(m):
    return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)


def _st(x, pan=0.0):
    """mono -> stereo, constant-power pan (scalar or per-sample array)."""
    a = (np.asarray(pan) + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)]) * np.sqrt(2)


def _interp(pts, t):
    p = np.asarray(pts, float)
    return np.interp(t, p[:, 0], p[:, 1])


def _fade_tail(x, sec=0.02):
    n = min(int(sec * SR), x.shape[-1])
    x[..., -n:] *= np.linspace(1, 0, n) ** 2
    return x


def glint(rng):
    L = int(1.2 * SR); tt = np.arange(L) / SR
    x = sum(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6)) * np.exp(-tt / d) * g
            for f, d, g in ((3520, 0.35, 0.5), (5274, 0.2, 0.3), (7040, 0.12, 0.2), (2637, 0.5, 0.25)))
    x *= 1 - np.exp(-tt / 0.002)
    return _fade_tail(_st(x * 0.5, 0.1))


def swell(rng, t0, t1):
    """Reverse cymbal: filtered noise whose envelope rises (exp) to t1, then a 60 ms release."""
    L1 = int((t1 - t0) * SR); L2 = int(0.06 * SR); tt = np.arange(L1) / SR
    n = sosfilt(_sos("high", 2500), rng.standard_normal(L1 + L2))
    env = np.concatenate([np.exp((tt - tt[-1]) / max((t1 - t0) / 4, 1e-3)), np.linspace(1, 0, L2) ** 2])
    sh = 0.6 + 0.4 * np.sin(2 * np.pi * np.arange(L1 + L2) / SR * 7.0)      # slight shimmer
    l = n * env * sh; r = np.roll(n, 37) * env * sh
    return np.stack([l, r]) * 0.5


def thud(rng, t0, t1):
    s = swell(rng, t0, t1) * 0.6
    L = int(1.0 * SR); tt = np.arange(L) / SR
    f = 55 + 70 * np.exp(-tt / 0.04)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.22) * (1 - np.exp(-tt / 0.003))
    out = np.zeros((2, s.shape[1] + L))
    out[:, :s.shape[1]] += s
    i = int((t1 - t0) * SR); out[:, i:i + L] += _st(body * 0.9)
    return _fade_tail(out)


def roll(rng, t0, t1):
    """Clicks speed up from ~6/s to ~40/s, then one heavier catch at t1."""
    D = t1 - t0; L = int((D + 0.4) * SR); out = np.zeros(L)
    click_len = int(0.012 * SR); ct = np.arange(click_len) / SR
    t, k = 0.0, 0
    while t < D:
        u = t / D
        c = sosfilt(_sos("band", [1800, 6000]), rng.standard_normal(click_len)) * np.exp(-ct / 0.0025)
        i = int(t * SR); out[i:i + click_len] += c * (0.35 + 0.35 * u) * (1.0 if k % 2 else 0.8)
        t += 1 / (6 + 34 * u ** 1.6); k += 1
    cl = int(0.12 * SR); cc = np.arange(cl) / SR
    catch = sosfilt(_sos("band", [900, 4000]), rng.standard_normal(cl)) * np.exp(-cc / 0.015)
    catch += np.sin(2 * np.pi * 1760 * cc) * np.exp(-cc / 0.03) * 0.4
    i = int(D * SR); out[i:i + cl] += catch * 0.9
    return _fade_tail(_st(out * 0.6, -0.15))


def glide(rng, pts, pan=None, level=0.35):
    p = np.asarray(pts, float); t0, t1 = p[0, 0], p[-1, 0]
    L = int((t1 - t0 + 0.6) * SR); tt = t0 + np.arange(L) / SR
    m = _interp(p, np.minimum(tt, t1))
    f = _hz(m) * (1 + 0.003 * np.sin(2 * np.pi * 5.2 * (tt - t0)))           # light vibrato
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    env = np.clip((tt - t0) / 0.08, 0, 1) * np.where(tt <= t1, 1.0, np.exp(-(tt - t1) / 0.15))
    pn = _interp(pan, np.minimum(tt, t1)) if pan is not None else 0.0
    return _fade_tail(_st(x * env * level, pn))


def whine(rng, pts, level=0.22):
    """Electric motor: pitch exp-mapped 160 -> 1500 Hz by speed, gear partial a ninth above, brightness and level rise."""
    p = np.asarray(pts, float); t0, t1 = p[0, 0], p[-1, 0]
    L = int((t1 - t0 + 0.5) * SR); tt = t0 + np.arange(L) / SR
    s = np.clip(_interp(p, np.minimum(tt, t1)), 0, 1)
    f = 160 * (1500 / 160) ** s
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.35 * np.sin(2.25 * ph) + (0.15 + 0.25 * s) * np.sin(3 * ph) + 0.08 * np.sin(4.5 * ph)
    x += sosfilt(_sos("band", [2000, 7000]), rng.standard_normal(L)) * (0.05 + 0.1 * s)   # air/rush
    env = np.clip((tt - t0) / 0.05, 0, 1) * (0.35 + 0.65 * s ** 0.7)
    env *= np.where(tt <= t1, 1.0, np.exp(-(tt - t1) / 0.12))
    return _fade_tail(_st(x * env * level, 0.0))


def rewind(rng, t0, t1):
    """Tape fast-rewind: a warbling squeal (pitch ~2.2-3.5 kHz wobbling) over a spool whirr, slowing at the end + clunk."""
    D = t1 - t0; L = int((D + 0.25) * SR); tt = np.arange(L) / SR
    u = np.clip(tt / D, 0, 1)
    slow = 1 - 0.55 * np.clip((u - 0.8) / 0.2, 0, 1) ** 2                    # last 20 %: winds down
    fq = (2200 + 1300 * np.sin(2 * np.pi * 11 * tt) * 0.5 + 600 * rng.standard_normal(L).cumsum() / np.sqrt(SR * 40)) * slow
    sq = np.sin(2 * np.pi * np.cumsum(np.clip(fq, 300, 6000)) / SR)
    chatter = sosfilt(_sos("band", [1500, 8000]), rng.standard_normal(L)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 37 * slow * tt)))
    whirr = sosfilt(_sos("band", [180, 900]), rng.standard_normal(L)) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * slow * tt))
    x = (0.25 * sq + 0.35 * chatter + 0.5 * whirr) * np.where(tt <= D, np.clip(tt / 0.03, 0, 1), np.exp(-(tt - D) / 0.04))
    cl = int(0.15 * SR); ct = np.arange(cl) / SR
    clunk = np.sin(2 * np.pi * (90 + 120 * np.exp(-ct / 0.01)) * ct) * np.exp(-ct / 0.05) + \
        sosfilt(_sos("band", [600, 3000]), rng.standard_normal(cl)) * np.exp(-ct / 0.01) * 0.5
    i = int(D * SR); x[i:i + cl] += clunk[:max(0, min(cl, L - i))] * 0.8
    pan = 0.25 * np.sin(2 * np.pi * 3 * tt)
    return _fade_tail(_st(x * 0.45, pan))


def shimmer(rng, t0, t1, notes):
    D = t1 - t0; L = int((D + 1.5) * SR); out = np.zeros((2, L))
    n = max(int(D * 14), 4)
    for k in range(n):
        t = D * (k / (n - 1)) ** 0.85 + rng.normal(0, 0.008)
        m = notes[k % len(notes)] + 12 * (k * 2 // n)
        dl = int(0.6 * SR); dt = np.arange(dl) / SR
        f = _hz(m)
        x = (np.sin(2 * np.pi * f * dt) + 0.3 * np.sin(2 * np.pi * 2 * f * dt)) * np.exp(-dt / 0.18) * (1 - np.exp(-dt / 0.002))
        i = int(max(t, 0) * SR); pan = -0.7 + 1.4 * k / (n - 1)
        out[:, i:i + dl] += _st(x, pan)[:, :max(0, min(dl, L - i))] * (0.12 + 0.1 * rng.random())
    return _fade_tail(out)
