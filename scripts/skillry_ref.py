#!/usr/bin/env python3
"""取一条 Skillry / awesome-opus5-5-videos 案例当风格参考（不入库）。

用法：
  python3 skillry_ref.py <Skillry 链接 | 仓库 prompts/<slug>.md 链接 | X 原帖链接 | slug> [--x] [--no-pull]

产物 $OPUS_HOME/_refs/clips/<slug>/（OPUS_HOME 默认 ~/opus-video）：
  original.mp4    Skillry 托管的原作（转码，≈720p；一定是页面上那一段，声音与原帖一致，原作无声则无声）
  original_x.mp4  --x 时从 X 原帖取的原画质（走代理；一帖多视频时按时长挑）
  prompt.md       仓库里的提示词文件（部分条目只有原帖文字，文件里会注明）
  sheet_NN.jpg    4×4 拼板，每格左上角标秒数
  meta.json       videos.json 里这一条 + 时长/分辨率
注意：同目录下 Skillry 还有 remake.mp4，是 Skillry 自己的重做版，不是原作，本脚本不取。
"""
import argparse, json, math, os, re, shutil, subprocess, sys, urllib.request
from pathlib import Path

HOME = Path(os.environ.get("OPUS_HOME", Path.home() / "opus-video"))
REPO = HOME / "_refs/awesome-opus5-5-videos"
CLIPS = HOME / "_refs/clips"
UA = {"User-Agent": "Mozilla/5.0"}


def sh(*a, **k):
    return subprocess.run(a, check=True, text=True, capture_output=True, **k).stdout


def probe(p):
    j = json.loads(sh("ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(p)))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    return {"duration": round(float(j["format"]["duration"]), 2), "width": v["width"], "height": v["height"],
            "audio": any(s["codec_type"] == "audio" for s in j["streams"])}


def find_entry(arg, videos):
    by_slug = {x["slug"]: x for x in videos}
    m = re.search(r"opus-5-5/([A-Za-z0-9_-]+)", arg) or re.search(r"prompts/([A-Za-z0-9_-]+)\.md", arg)
    if m and m.group(1) in by_slug:
        return by_slug[m.group(1)]
    m = re.search(r"status/(\d+)", arg)
    if m:
        for x in videos:
            if x["post_url"].endswith(m.group(1)):
                return x
    if arg in by_slug:
        return by_slug[arg]
    sys.exit(f"找不到这一条：{arg}（先 git pull 仓库再试；仍找不到说明不在收录里）")


def fetch_skillry(entry, out):
    html = urllib.request.urlopen(urllib.request.Request(entry["skillry_url"], headers=UA), timeout=60).read().decode()
    slug = re.escape(entry["slug"])
    m = re.search(rf"https://media\.skillry\.dev/opus-5-5/{slug}/original\.mp4", html)
    if not m:  # 页面没给原片时退到卡片预览（较短）
        m = re.search(rf"https://media\.skillry\.dev/opus-5-5/{slug}/original-card\.[0-9a-f]+\.mp4", html)
    if not m:
        sys.exit("Skillry 页面里没找到原片地址")
    with urllib.request.urlopen(urllib.request.Request(m.group(0), headers=UA), timeout=120) as r, open(out, "wb") as f:
        shutil.copyfileobj(r, f)
    return m.group(0)


def fetch_x(entry, out, want_dur):
    # 默认格式会选中只有画面的 HLS 流（实测 3/10 条无声），指定 https 直链格式
    base = ["yt-dlp", "-q", "--no-warnings", "-f", "b[protocol=https]/b"]
    info = json.loads(sh("yt-dlp", "-q", "--no-warnings", "--flat-playlist", "-J", entry["post_url"]))
    items = info.get("entries") or [info]
    pick = ""
    if len(items) > 1 and want_dur:  # 一帖多视频：按 Skillry 原片时长挑最接近的一个
        i = min(range(len(items)), key=lambda k: abs((items[k].get("duration") or 0) - want_dur))
        pick = str(i + 1)
    sh(*base, *(["--playlist-items", pick] if pick else []), "-o", str(out), entry["post_url"])
    return len(items)


def sheets(video, outdir, dur):
    fps = min(4.0, 48.0 / max(dur, 1))  # 约 48 格：短片每 0.25 s 一格，长片均匀铺满
    for old in outdir.glob("sheet_*.jpg"):
        old.unlink()
    vf = (f"fps={fps},scale=480:-2,"
          "drawtext=text='%{pts\\:flt}s':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.6,"
          "tile=4x4:padding=4:color=black")
    sh("ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", vf, str(outdir / "sheet_%02d.jpg"))
    return math.ceil(dur * fps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--x", action="store_true", help="另取 X 原帖原画质（小字多、720p 看不清时用）")
    ap.add_argument("--no-pull", action="store_true")
    a = ap.parse_args()
    if not REPO.exists():
        sys.exit(f"仓库不在 {REPO}：git clone https://github.com/yihui-dev/awesome-opus5-5-videos {REPO}")
    if not a.no_pull:
        subprocess.run(["git", "-C", str(REPO), "pull", "-q"], check=False)
    videos = json.loads((REPO / "data/videos.json").read_text())
    e = find_entry(a.ref, videos)
    out = CLIPS / e["slug"]; out.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "prompts" / f"{e['slug']}.md", out / "prompt.md")
    src = fetch_skillry(e, out / "original.mp4")
    meta = dict(e, skillry_mp4=src, skillry=probe(out / "original.mp4"))
    if a.x:
        meta["x_items"] = fetch_x(e, out / "original_x.mp4", meta["skillry"]["duration"])
        meta["x"] = probe(out / "original_x.mp4")
        if abs(meta["x"]["duration"] - meta["skillry"]["duration"]) > 1:
            print(f"⚠️ X 取到的时长 {meta['x']['duration']}s ≠ Skillry {meta['skillry']['duration']}s，可能拿错了视频，以 original.mp4 为准")
    meta["frames"] = sheets(out / "original.mp4", out, meta["skillry"]["duration"])
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    s = meta["skillry"]
    print(f"{out}\n  {e['category']} · {', '.join(e['tech_tags'])}（标签是 Skillry 重做版用的技术）· "
          f"{s['duration']}s {s['width']}×{s['height']}{' 有声' if s['audio'] else ' 无声'}"
          f"{' · 提示词不完整（只有原帖文字）' if e['prompt_partial'] else ''}\n  拼板 {len(list(out.glob('sheet_*.jpg')))} 张")


if __name__ == "__main__":
    main()
