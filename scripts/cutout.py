"""纯色底抠图：生图时让角色/道具站在纯色底上，这里从四边泛洪去掉底色，输出裁到内容边界的 RGBA PNG。

用法（要 scipy，用 $OPUS_HOME/_venv/bin/python）：
  cutout.py <in.png> [<in2.png> ...] --out-dir <目录> [--tol 9]
--tol：与底色的色差阈值。底色干净时 9（生日项目 8 个 Q 版实测）；底色有渐变或噪点时调到 12~26。
只去掉和四边连通的底色，角色身上与底色相近的区域（白衣服、高光）不会被挖空。
"""
import argparse
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def cutout(path: str, tol: float) -> Image.Image:
    a = np.asarray(Image.open(path).convert("RGB")).astype(float)
    h, w, _ = a.shape
    corners = [a[:20, :20], a[:20, -20:], a[-20:, :20], a[-20:, -20:]]
    bg = np.median(np.concatenate([c.reshape(-1, 3) for c in corners]), axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(2))
    lab, _ = ndi.label(d < tol)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bgm = np.isin(lab, list(border))
    alpha = np.ones((h, w))
    alpha[bgm] = 0
    edge = ndi.binary_dilation(bgm, iterations=3) & ~bgm  # 只在贴着底色的边缘做软过渡
    alpha[edge] = np.clip((d[edge] - tol) / 14, 0, 1)
    alpha = ndi.gaussian_filter(alpha, 0.7)
    img = Image.fromarray(np.dstack([a, alpha * 255]).astype(np.uint8), "RGBA")
    bbox = img.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return img.crop(bbox)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tol", type=float, default=9)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    for p in args.inputs:
        img = cutout(p, args.tol)
        out = os.path.join(args.out_dir, os.path.splitext(os.path.basename(p))[0] + ".png")
        img.save(out)
        print(out, img.size)


if __name__ == "__main__":
    main()
