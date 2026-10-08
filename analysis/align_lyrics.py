"""Word-timed lyrics -> <project>/public/data/lyrics.json (the engine's Lyrics).

  python align_lyrics.py <project_dir> --lyrics lyrics.txt [--pron pron.json] [--windows windows.json] [--margin 1.5]
  python align_lyrics.py <project_dir> --whisper [--lang zh] [--model large-v3]

With lyric text (one sung line per text line, blank lines ignored) — the accurate path:
  CTC forced alignment, as in mexicat/pdoom-video: frame-wise character log-probs of the Demucs vocal stem
  from torchaudio's MMS_FA (multilingual, romanised characters), one global Viterbi pass over the whole
  song with a "garbage" star token between lines that absorbs ad-libs / backing vocals / instrumental
  (ctcalign.py). Chinese characters are aligned by their toneless pinyin (one "word" per character),
  Latin tokens by spelling; acronyms are spelled out letter by letter. Per-token overrides in --pron
  ({"NVDA": "en vee dee ay", "GPT": "gee pee tee"}).
  Not ported from the original: its second English-only acoustic model, the L/R-channel fusion, the manual
  anchors and the signal-based boundary refinement (they were tuned to one song). Check the result by eye
  in the preview (the info line shows the current lyric line). A line that landed seconds off (held notes,
  backing vocals, a repeated chorus line) gets a time window by ear — {"41": [136.5, 140.5]} in --windows —
  and a re-run; that is what the original did with its manual anchors. Wrong pronunciations: --pron.
Without text: faster-whisper word timestamps on the vocal stem (transcription errors included; use it to
get a first draft of the lyric text, then re-run with --lyrics).
"""
import common
import json
import re
import sys

import numpy as np

import ctcalign

CJK = r"㐀-䶿一-鿿豈-﫿"
PUNCT_AFTER = "，。！？、；：,.!?…”’」』）)~～—-"
LETTER = {"a": "ay", "b": "bee", "c": "see", "d": "dee", "e": "ee", "f": "eff", "g": "gee", "h": "aitch", "i": "eye",
          "j": "jay", "k": "kay", "l": "el", "m": "em", "n": "en", "o": "oh", "p": "pee", "q": "cue", "r": "are",
          "s": "ess", "t": "tee", "u": "you", "v": "vee", "w": "double you", "x": "ex", "y": "why", "z": "zee"}


def tokens(line):
    """Display tokens: each CJK character (with trailing punctuation attached), or a run of non-space Latin."""
    return re.findall(rf"[{CJK}][{re.escape(PUNCT_AFTER)}]*|[^\s{CJK}]+", line)


def make_pron(overrides):
    from pypinyin import lazy_pinyin, Style

    def pron(tok):
        if tok in overrides:
            return overrides[tok].split()
        core = tok.rstrip(PUNCT_AFTER)
        if core in overrides:
            return overrides[core].split()
        if re.match(rf"[{CJK}]", core):
            py = lazy_pinyin(core[0], style=Style.NORMAL, errors="ignore")
            return [re.sub(r"[^a-z]", "", p.replace("ü", "u").replace("v", "u")) for p in py if p] or ["a"]
        # acronym (2-5 capitals, maybe digits): spell it
        a = re.sub(r"[^A-Za-z0-9]", "", core)
        if 2 <= len(a) <= 5 and a.isupper():
            return " ".join(LETTER.get(c.lower(), c.lower()) for c in a if c.isalpha()).split()
        w = tok.lower().replace("’", "'")
        w = re.sub(r"[^a-z' ]", " ", w).strip("' ")
        return [p.strip("'") for p in w.split() if p.strip("'")] or ["a"]
    return pron


def mms_emissions(y16, chunk_s=20.0, ctx_s=3.0):
    """Frame-wise (20 ms) log-probs over ctcalign.ALPHA from torchaudio MMS_FA, chunked with context."""
    import torch
    import torchaudio
    bundle = torchaudio.pipelines.MMS_FA
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = bundle.get_model(with_star=False).to(dev).eval()
    labs = list(bundle.get_labels(star=None))
    HOP = 320
    y16 = y16 / (np.abs(y16).max() + 1e-9)
    n_frames = len(y16) // HOP
    chunk, ctx = int(chunk_s * 16000), int(ctx_s * 16000)
    em_all = None
    for s in range(0, len(y16), chunk):
        a, b = max(0, s - ctx), min(len(y16), s + chunk + ctx)
        x = torch.from_numpy(y16[a:b]).float()[None].to(dev)
        with torch.inference_mode():
            em, _ = model(x)
            em = torch.log_softmax(em, dim=-1)[0].float().cpu().numpy()
        if em_all is None:
            em_all = np.full((n_frames, em.shape[1]), np.nan, np.float32)
        f0 = a // HOP
        lo, hi = s // HOP, min(n_frames, (s + chunk) // HOP)
        seg = em[lo - f0: hi - f0]
        em_all[lo: lo + len(seg)] = seg
    last = np.where(~np.isnan(em_all[:, 0]))[0].max()
    em_all[last + 1:] = em_all[last]
    em = em_all.astype(np.float64)
    out = np.full((em.shape[0], len(ctcalign.ALPHA)), -1e4)
    blank_cols = [labs.index("-")] + ([labs.index("|")] if "|" in labs else [])
    out[:, 0] = np.logaddexp.reduce(em[:, blank_cols], axis=1)
    for i, c in enumerate(labs):
        k = c.lower()
        if k in ctcalign.AIDX and k != "-":
            out[:, ctcalign.AIDX[k]] = em[:, i]
    out -= np.logaddexp.reduce(out, axis=1, keepdims=True)
    return out


def align_text(proj, text_lines, overrides, margin, windows=None):
    import librosa
    y16 = librosa.resample(proj.load_stem("vocals", sr=common.SR), orig_sr=common.SR, target_sr=16000)
    E = mms_emissions(y16)
    lines_tokens = [tokens(l) for l in text_lines]
    spans, score, _, _ = ctcalign.align(E, lines_tokens, make_pron(overrides), margin=margin, line_windows=windows)
    table = ctcalign.word_table(spans, lines_tokens)
    lines = []
    for li, text in enumerate(text_lines):
        ws = [dict(w=r["w"], start=round(r["start"], 3), end=round(r["end"], 3), conf=round(r["conf"], 3)) for r in table if r["li"] == li]
        lines.append(dict(text=text, start=ws[0]["start"], end=ws[-1]["end"], words=ws))
    return lines, score


def whisper_lines(proj, lang, model_name):
    from faster_whisper import WhisperModel
    m = WhisperModel(model_name, device="cuda", compute_type="float16", download_root=str(common.MODELS / "whisper"))
    segs, info = m.transcribe(str(proj.stems / "vocals.wav"), language=lang, word_timestamps=True, vad_filter=True, beam_size=5)
    lines = []
    for s in segs:
        ws = [dict(w=w.word.strip(), start=round(w.start, 3), end=round(w.end, 3), conf=round(w.probability, 3)) for w in (s.words or []) if w.word.strip()]
        if ws:
            sep = "" if re.search(rf"[{CJK}]", s.text) else " "
            lines.append(dict(text=sep.join(w["w"] for w in ws), start=ws[0]["start"], end=ws[-1]["end"], words=ws))
    return lines, info.language


def main():
    args = sys.argv[1:]
    proj = common.Project(args[0])
    get = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if "--lyrics" in args:
        text_lines = [l.strip() for l in open(get("--lyrics"), encoding="utf-8") if l.strip()]
        overrides = json.load(open(get("--pron"), encoding="utf-8")) if get("--pron") else {}
        # --windows: {"<line index, 0-based>": [earliest start s, latest end s]} for lines the free pass got wrong
        windows = {int(k): tuple(v) for k, v in json.load(open(get("--windows"), encoding="utf-8")).items()} if get("--windows") else None
        lines, score = align_text(proj, text_lines, overrides, float(get("--margin", "1.5")), windows)
        note = f"CTC forced alignment (MMS_FA + global Viterbi), score {score:.1f}"
    else:
        lines, lang = whisper_lines(proj, get("--lang"), get("--model", "large-v3"))
        note = f"faster-whisper word timestamps (unconstrained transcription, language {lang})"
    doc = dict(lines=[dict(i=i, **l) for i, l in enumerate(lines)], notes=note)
    (proj.data / "lyrics.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    low = [(l["text"], w["w"], w["conf"]) for l in lines for w in l["words"] if w.get("conf", 1) < 0.2]
    print("wrote", proj.data / "lyrics.json", f"{len(lines)} lines, {sum(len(l['words']) for l in lines)} words; {note}")
    for l in lines:
        print(f"  {l['start']:7.2f}-{l['end']:7.2f}  {l['text']}")
    if low:
        print(f"low-confidence words ({len(low)}): " + "; ".join(f"{w}@{t[:12]}" for t, w, _ in low[:20]))


if __name__ == "__main__":
    main()
