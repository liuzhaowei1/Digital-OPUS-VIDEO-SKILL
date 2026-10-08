"""Decode the song gaplessly and split it into Demucs stems (vocals / drums / bass / other).

  python separate.py <project_dir> <song file> [--model htdemucs_ft]

Decoding with ffmpeg first matters: mp3 encoder delay trimming differs between decoders (the original
pdoom repo had to shift its stems by 23 ms). Demucs then runs on our wav, so stems share mix.wav's timeline.
htdemucs_ft is 4 models (best vocals, ~4x slower); htdemucs is one. Runs on CUDA when available.
"""
import common
import subprocess
import sys
import shutil
from pathlib import Path


def main():
    args = sys.argv[1:]
    proj = common.Project(args[0])
    song = Path(args[1]).resolve()
    model = args[args.index("--model") + 1] if "--model" in args else "htdemucs_ft"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(song), "-ac", "2", "-ar", str(common.SR), "-c:a", "pcm_f32le", str(proj.mix)], check=True)
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tmp = proj.an / "demucs_out"
    subprocess.run([sys.executable, "-m", "demucs", "-n", model, "-d", dev, "--float32", "-o", str(tmp), str(proj.mix)], check=True)
    out = tmp / model / proj.mix.stem
    for n in ("vocals", "drums", "bass", "other"):
        shutil.move(str(out / f"{n}.wav"), proj.stems / f"{n}.wav")
    shutil.rmtree(tmp, ignore_errors=True)
    # sanity: stems must sum back to the mix with no time offset
    import numpy as np
    mix = proj.load_mix()
    s = sum(proj.load_stem(n)[: len(mix)] for n in ("vocals", "drums", "bass", "other"))
    n = min(len(mix), len(s), common.SR * 30)
    a, b = mix[:n], s[:n]
    lags = range(-2000, 2001, 5)
    best = max(lags, key=lambda L: float(np.dot(a[max(0, L):n + min(0, L)], b[max(0, -L):n - max(0, L)])))
    print(f"stems -> {proj.stems}  ({model} on {dev}); stem/mix lag {best} samples ({best / common.SR * 1000:.1f} ms, expect 0)")


if __name__ == "__main__":
    main()
