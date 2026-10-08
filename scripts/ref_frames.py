#!/usr/bin/env python3
"""拆参考片第一步：按画面变化抽「唯一画面」关键帧 + 编号拼板，供 Claude 读图写风格分析。

用法（用分析环境：$OPUS_HOME/_venv/bin/python，需要 numpy、Pillow、scipy；系统里要有 ffmpeg/ffprobe）：
  python ref_frames.py <视频> --out <目录> [--fps N] [--from 秒] [--to 秒] [--extra-sec 12.5,40]

产物（<目录>/）：
  key/kNNN_MMSS.jpg   唯一画面帧（全分辨率）
  tiny/               按 fps 的全部原始帧（存疑时回看）
  index.json          [{file, path, t_sec, start_sec, end_sec, kind}]，kind = scene / extra
  sheet_NN.jpg        16 帧一张的编号拼板（先看拼板，再按需开原图）
stdout：一行 JSON 摘要 {"frames", "fps", "sheets", "index", "long_segments"}

做法：按 fps 全解码 → 与当前段代表帧比对切段（底部字幕区变化也切段）→ 段内取最稳定帧
      → 感知哈希全局去重（能识别切走又切回）。
参数取舍（三部视频对照测试后定）：
  - fps 按时长：≤3 分钟 4fps，≤10 分钟 2fps，更长 1fps。1fps 会漏掉快速蒙太奇里停留不足 1 秒的画面
  - 字幕区单独检测：深色底 + 字幕切换，全画面像素差达不到阈值，不单独测会整句丢失
已知会漏的两类画面（读完拼板要回头查）：
  - 暗、低对比的整段会被判成一张：long_segments 列出持续 >3 秒的段，去 tiny/ 回看
  - 停留不足一个采样间隔的闪现帧：提高 --fps，或用 --extra-sec 按秒补截
"""
import argparse, glob, json, os, shutil, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.fft import dct

PER_SHEET, COLS, TILE_W = 16, 4, 400
SEG_TH, PHASH_TH, CAP_BAND, CAP_TH = 7.0, 5, (0.86, 0.97), 6.0


def pick_fps(duration):
    return 4 if duration <= 180 else 2 if duration <= 600 else 1


def probe(video):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                                   "-show_streams", str(video)], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return float(j["format"]["duration"]), int(v["width"]), int(v["height"])


def phash(im):
    """64 位感知哈希（32×32 灰度 → 二维 DCT → 左上 8×8 与中位数比较），与 imagehash.phash 同法。"""
    a = np.asarray(im.convert("L").resize((32, 32), Image.LANCZOS), dtype=np.float64)
    low = dct(dct(a, axis=0, norm="ortho"), axis=1, norm="ortho")[:8, :8]
    return (low > np.median(low)).flatten()


def fmt(t):
    t = int(t)
    return f"{t // 60:02d}{t % 60:02d}"


def extract(video, t0, dur, out, fps):
    for d in ("tiny", "key"):
        shutil.rmtree(out / d, ignore_errors=True)
        (out / d).mkdir(parents=True)
    # 只解码一次、输出全分辨率帧，分析用内存缩放副本（不要改成分析后再用 -ss 重抽：-ss 在 -i 前有数秒误差）
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t0), "-i", str(video), "-t", str(dur),
                    "-vf", f"fps={fps}", "-q:v", "3", str(out / "tiny/t%05d.jpg"), "-y"], check=True)
    fs = sorted(glob.glob(str(out / "tiny/*.jpg")))
    if not fs:
        sys.exit("没有解码出帧：检查视频路径和 --from/--to")
    ims = []
    for f in fs:
        with Image.open(f) as im:
            g = im.convert("L")
            ims.append(np.asarray(g.resize((400, max(1, int(400 * g.height / g.width)))), dtype=np.float32))
    n = len(ims)
    h = ims[0].shape[0]
    y0, y1 = int(h * CAP_BAND[0]), int(h * CAP_BAND[1])
    diff = lambda i, j: float(np.mean(np.abs(ims[i] - ims[j])))
    capdiff = lambda i, j: float(np.mean(np.abs(ims[i][y0:y1] - ims[j][y0:y1])))

    segs, start = [], 0
    for i in range(1, n):
        if diff(i, start) > SEG_TH or capdiff(i, start) > CAP_TH:
            segs.append((start, i - 1)); start = i
    segs.append((start, n - 1))

    reps = []
    for a, b in segs:
        if a == b:
            reps.append((a, a, b)); continue
        best = min(range(a, b + 1), key=lambda i: (diff(i, max(a, i - 1)) + diff(i, min(b, i + 1))) / 2)
        reps.append((best, a, b))

    uniq, seen = [], []
    for idx, a, b in reps:
        with Image.open(fs[idx]) as im:
            hsh = phash(im)
        dup = any(int(np.count_nonzero(hsh != hh)) <= PHASH_TH and capdiff(idx, si) <= CAP_TH for hh, si in seen)
        if not dup:
            seen.append((hsh, idx)); uniq.append((idx, a, b))
    return fs, n, len(segs), uniq


def make_sheets(entries, out):
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for old in out.glob("sheet_*.jpg"):
        old.unlink()
    sheets = []
    for s in range(0, len(entries), PER_SHEET):
        chunk = entries[s:s + PER_SHEET]
        ims = [Image.open(e["path"]) for e in chunk]
        th = int(TILE_W * ims[0].height / ims[0].width)
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TILE_W, rows * th), "white")
        d = ImageDraw.Draw(sheet)
        for i, (im, e) in enumerate(zip(ims, chunk)):
            x, y = (i % COLS) * TILE_W, (i // COLS) * th
            sheet.paste(im.convert("RGB").resize((TILE_W, th)), (x, y))
            t = int(e["t_sec"])
            d.rectangle([x, y, x + 150, y + 28], fill="black")
            d.text((x + 4, y + 2), f"{e['file'][:4]} {t // 60:02d}:{t % 60:02d}", fill="yellow", font=font)
            im.close()
        p = out / f"sheet_{s // PER_SHEET + 1:02d}.jpg"
        sheet.save(p, quality=85)
        sheets.append(str(p))
    return sheets


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, help="覆盖按时长自动选的帧率")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--extra-sec", default="", help="逗号分隔的秒数，按秒补截（漏掉的闪现帧、暗场段）")
    a = ap.parse_args()

    video, out = Path(a.video), Path(a.out)
    duration, w, h = probe(video)
    t1 = min(a.t1 or duration, duration)
    fps = a.fps or pick_fps(t1 - a.t0)
    fs, n, nseg, uniq = extract(video, a.t0, t1 - a.t0, out, fps)

    entries = []
    for k, (idx, s, e) in enumerate(uniq, 1):
        t = a.t0 + idx / fps
        name = f"k{k:03d}_{fmt(t)}.jpg"
        shutil.copy(fs[idx], out / "key" / name)
        entries.append({"file": name, "path": str(out / "key" / name), "t_sec": round(t, 2),
                        "start_sec": round(a.t0 + s / fps, 2), "end_sec": round(a.t0 + (e + 1) / fps, 2), "kind": "scene"})
    for sec in [float(x) for x in a.extra_sec.split(",") if x.strip()]:
        name = f"x{len(entries) + 1:03d}_{fmt(sec)}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ss", str(sec), "-frames:v", "1", "-q:v", "3",
                        str(out / "key" / name), "-y"], check=True)
        entries.append({"file": name, "path": str(out / "key" / name), "t_sec": sec, "start_sec": sec, "end_sec": sec, "kind": "extra"})
    entries.sort(key=lambda e: e["t_sec"])

    (out / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    sheets = make_sheets(entries, out)
    long_segs = [[e["start_sec"], e["end_sec"]] for e in entries if e["kind"] == "scene" and e["end_sec"] - e["start_sec"] > 3]
    print(json.dumps({"video": str(video), "size": f"{w}x{h}", "duration": round(duration, 2), "fps": fps,
                      "decoded": n, "segments": nseg, "frames": len(entries), "sheets": sheets,
                      "index": str(out / "index.json"), "long_segments": long_segs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
