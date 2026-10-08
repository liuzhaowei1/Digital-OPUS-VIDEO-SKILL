# 环境：装什么、装在哪、怎么自检

所有共用组件放在 `$OPUS_HOME`（默认 `~/opus-video`），不进 skill 目录、不进 git。按需装：只做 Remotion 动效的，装「基础」几项 + Remotion 工作区即可；要卡拍、配旁白、合成 BGM、拆参考片的再装「分析环境」。

| 组件 | 位置 | 什么时候需要 | 安装 |
|---|---|---|---|
| Node.js ≥ 20、ffmpeg/ffprobe、git | 系统 | 基础，都要 | 系统包管理器 |
| 字体（~134 MB） | `$OPUS_HOME/_assets/fonts/` | 基础，都要 | 见「字体」 |
| Chromium（内置引擎渲染用） | `~/.cache/ms-playwright/chromium-*/` | 内置引擎 | `npx playwright-core install chromium`（或用 `OPUS_CHROME` 指向已有的 Chrome/Chromium） |
| Remotion 工作区 | `$OPUS_REMOTION`（默认 `$OPUS_HOME/remotion-base`） | Remotion 路线 | `bash scripts/setup-remotion.sh` |
| 分析用 Python 环境（torch、demucs、librosa…） | `$OPUS_HOME/_venv/` | 按歌/按旁白做画面、合成 BGM、拆参考片 | 见「分析环境」 |
| 模型（demucs、MMS_FA、whisper） | `$OPUS_HOME/_models/` | 同上 | 首次运行自动下载，约 1.6 GB（+3 GB whisper）；**要长期保留** |
| JIT/字体缓存（numba、matplotlib） | `~/.cache/opus-video/` | — | 自动建，可随时删 |
| 真实乐器（Surge XT、GM 音色库） | `$OPUS_HOME/_plugins/`、系统 | 合成 BGM 想用真实乐器音色时 | 见「真实乐器」 |
| 参考案例库（awesome-opus5-5-videos） | `$OPUS_HOME/_refs/` | 想从该案例库取参考片时 | `git clone https://github.com/yihui-dev/awesome-opus5-5-videos $OPUS_HOME/_refs/awesome-opus5-5-videos` |
| 风格库（拆过的参考片） | `$OPUS_LIBRARY`（默认 `$OPUS_HOME/library`） | — | 拆参考片时自动建（`docs/REFERENCE.md`） |

可选 API（只在用到时需要）：

| 用途 | 环境变量 | 说明 |
|---|---|---|
| 生图出静态素材（`scripts/gen_image.sh`） | `OPENAI_API_KEY`（或 `OPUS_IMAGE_KEY_FILE`） | OpenAI 图像接口，按张计费 |
| TTS 配旁白（`scripts/tts.py`） | `DASHSCOPE_API_KEY`（或 `--key-file`） | 阿里云百炼 Qwen-TTS；`pip install dashscope` |

各片子的文件：代码工作区 `$OPUS_HOME/<日期>_<slug>/`（引擎项目各自 git init），成片与过程产物 `$OPUS_DELIVER/<日期>_<slug>/`（默认 `$OPUS_HOME/films`）。WSL 用户可以把 `OPUS_DELIVER` 设成 `/mnt/c/...` 下的目录，在 Windows 资源管理器里直接看片；代码工作区留在 Linux 文件系统里（node_modules 放 `/mnt/c` 会很慢，vite 也收不到改动通知）。

## 字体
```bash
F=${OPUS_HOME:-~/opus-video}/_assets/fonts; mkdir -p $F/cjk-src
# 拉丁字体：Archivo（宽度×字重静态实例）、Cormorant、IBM Plex Mono、单笔画字体——取自 mexicat/pdoom-video 的 app/public/fonts/
git clone --depth 1 https://github.com/mexicat/pdoom-video /tmp/pdoom && cp -r /tmp/pdoom/app/public/fonts/* $F/
# 中文：Google Fonts 的思源黑体/宋体可变字重版（OFL），切出静态字重（opentype.js 取轮廓要静态字重；需要 pip install fonttools）
cd $F/cjk-src && curl -sSfL -o 'NotoSansSC[wght].ttf' 'https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf' \
  && curl -sSfL -o 'NotoSerifSC[wght].ttf' 'https://github.com/google/fonts/raw/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf' \
  && curl -sSfL -O https://github.com/google/fonts/raw/main/ofl/notosanssc/OFL.txt
cd $F && for w in 300 500 700 900; do python3 -m fontTools.varLib.instancer "cjk-src/NotoSansSC[wght].ttf" wght=$w -o NotoSansSC-$w.ttf -q; done \
  && for w in 400 700 900; do python3 -m fontTools.varLib.instancer "cjk-src/NotoSerifSC[wght].ttf" wght=$w -o NotoSerifSC-$w.ttf -q; done
```
许可：Archivo、Cormorant Garamond、IBM Plex Mono、Noto Sans/Serif SC 均为 SIL OFL；单笔画字体来自 hersheytext（OFL/公有领域）。

## 分析环境
```bash
cd ${OPUS_HOME:-~/opus-video} && uv venv --python 3.12 _venv
# 有 NVIDIA 显卡：CUDA 版 torch（分轨快很多）；没有就去掉 --index-url 装 CPU 版
uv pip install --python _venv/bin/python torch torchaudio --index-url https://download.pytorch.org/whl/cu124
uv pip install --python _venv/bin/python -r <skill 目录>/analysis/requirements.txt
```
跑分析一律用 `$OPUS_HOME/_venv/bin/python`，别往系统 Python 里装。

## 真实乐器（BGM 的 `voices`，可选）
| 组件 | 位置 | 安装 |
|---|---|---|
| Surge XT 1.3.4（VST3 + 出厂音色，~600 MB） | `$OPUS_HOME/_plugins/surge-xt/` | `mkdir -p $OPUS_HOME/_plugins/surge-xt && curl -L https://github.com/surge-synthesizer/releases-xt/releases/download/1.3.4/surge-xt-linux-x86_64-1.3.4.tar.gz \| tar xz -C $OPUS_HOME/_plugins/surge-xt` |
| pedalboard、mido | `_venv` | 已在 `analysis/requirements.txt` |
| fluidsynth + FluidR3 GM SoundFont | 系统（`/usr/share/sounds/sf2/FluidR3_GM.sf2`） | `sudo apt install fluidsynth fluid-soundfont-gm` |

路径可用环境变量 `SURGE_XT`、`GM_SF2` 覆盖。⚠️ Surge 加载音色后的第一段渲染是静音（状态在第一个音频块才生效），`instruments.py` 已先空跑 0.3 秒。

## 内置引擎的 GPU 自检
内置引擎在无头 Chromium 里跑 WebGL。默认 WebGL 可能落到 SwiftShader（CPU 软件渲染）：画面正确，但光线步进类场景会慢几百倍（实测单帧 ~6 s vs GPU ~10–20 ms）。

- 自检：项目目录里 `node scripts/render.mjs gpu`，打印的渲染器应是你的显卡；打印 SwiftShader 就是没用上 GPU
- `render.mjs` 内置的参数在 **WSL2 + NVIDIA 笔记本显卡**上实测通过：`--use-gl=angle --use-angle=gl`（ANGLE 走 OpenGL → Mesa 的 D3D12 驱动 → 真 GPU）+ 环境变量 `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`（双显卡机器默认会选中核显）+ `--disable-accelerated-2d-canvas`（Canvas2D 留在 CPU 内存，纹理上传省一半时间）
- 其他平台（原生 Linux、macOS、Windows）未实测：自检不过时，用 `OPUS_EXTRA_ARGS` 追加 Chromium 参数试，或加 `--cpu` 用软件渲染先出片
- WSL2 上 `--use-angle=vulkan` 在没有 Vulkan ICD 时会退回 SwiftShader，不要用
> 实测组合（2026-09-29）：Chromium 1228（playwright 缓存）、Mesa 23.2.1、Node 22、torch 2.6.0+cu124

## 模型下载（首次运行自动下，慢且会断）
| 模型 | 用途 | 大小 | 位置 |
|---|---|---|---|
| HTDemucs-ft（4 个子模型） | 分轨 | 4 × 84 MB | `_models/hf/hub/models--adefossez--HTDemucs-ft/`（HuggingFace） |
| MMS_FA | 歌词/旁白强制对齐 | 1 262 047 414 字节 | `_models/torch/hub/checkpoints/model.pt` |
| faster-whisper large-v3 | 没有歌词文本时转写 | ~3 GB | `_models/whisper/`（只在 `--whisper` 时下） |

⚠️ **torch hub 下载断线会把残缺文件当成完整的 `model.pt`**（不校验大小），之后每次都报 `PytorchStreamReader failed reading zip archive: failed finding central directory`。恢复：
```bash
cd $OPUS_HOME/_models/torch/hub/checkpoints
curl -C - --retry 5 -o model.pt https://dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt   # 断点续传
stat -c %s model.pt    # 必须 = 1262047414
```
首次跑分析前先告诉用户要下载多少、大概等多久。
