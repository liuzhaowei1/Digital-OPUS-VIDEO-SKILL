# 内置引擎指南（three.js 逐帧确定性渲染）

来源：mexicat/pdoom-video（MIT，`engine/LICENSE`），2026-09-29 取自提交 `bdbad53` 并泛化。原版文档逐字保存在 `docs/upstream/`（ENGINE.md 是场景 API 的权威说明，TREATMENT.md 是一份完整方案书实例）。本文件只写**怎么用**和**与原版的差异**。

## 什么时候用它
着色器质感（版画排线、光线步进 3D、辉光、胶片颗粒）、高品质排版、严格卡拍、要 4K 或真运动模糊的片子。纯 DOM/CSS/SVG 动效、数据图表类快片用 Remotion 更快上手（`docs/REMOTION.md`）。

## 项目生命周期
```bash
bash <skill 目录>/scripts/new-project.sh <slug>     # → 代码 $OPUS_HOME/<日期>_<slug>/（模板 + npm install + git init）+ 交付文件夹 $OPUS_DELIVER/<日期>_<slug>/，deliver 软链过去
cd $OPUS_HOME/<日期>_<slug>
npx vite                                                            # 预览：浏览器开 http://localhost:5173（?t=12 从 12 秒起）
node scripts/render.mjs gpu                                          # 应打印你的显卡；打印 SwiftShader 见 SETUP.md
node scripts/render.mjs stills --t 1,4.5,7 --only <场景id> --out deliver/静帧   # 静帧，用 Read 看
node scripts/render.mjs sheet --from 0 --to 30 --n 16 --out deliver/静帧/sheet.png   # 拼板自查
node scripts/render.mjs sheet --cuts --out deliver/静帧/cuts.png              # 每个切点前后 4 帧：查转场
node scripts/render.mjs video --samples 4 --fps 30 --out deliver/草稿/draft.mp4       # 草稿
node scripts/render.mjs video --samples auto --shutter 0.2 --out out/final.mp4  # 成片（60fps、自适应运动模糊），再拷到 deliver/<日期>_<slug>.mp4
```
不带 `--out` 时默认写 `out/`（代码工作区内，临时）。成片先落 `out/` 再拷：长时间编码直写交付文件夹，中途失败会留半个文件在用户眼前。目录约定见 SKILL.md「项目文件放哪」。

## 项目结构（与原版不同处加粗）
| 路径 | 内容 |
|---|---|
| **`public/project.json`** | 时长、`audio`（歌曲路径，可省略=无声片）、无歌时的 `bpm`/`beatOffset`/`beatsPerBar`、`cjk`、`readout` |
| `public/audio/` | 歌曲 |
| `public/data/audio.json` | 节拍/小节/段落/包络/鼓与人声起音（`analysis/analyze_audio.py` 生成）；**缺省时用 project.json 的恒定节拍网格** |
| `public/data/lyrics.json` | 逐词歌词（`analysis/align_lyrics.py` 生成）；**缺省时为空** |
| `src/timeline.ts` | 剪辑：哪个场景何时出场。有歌时按歌词行定切点再吸附到拍（范例 `examples/timeline.pdoom.ts`）；无歌走网格合成 BGM 时从项目根目录的 `cues.json` 读切点（范例 `examples/timeline.cues.ts` + `examples/cues.example.json`，需 tsconfig 的 `resolveJsonModule`，模板已开） |
| `src/scenes/*.ts` | 场景，一个文件一个 `Scene` 子类；模板带 `demo.ts`（着色器 + 线批 + 中文排版 + 卡拍各一例），开工后删掉 |
| `src/engine/` | 引擎，一般不改 |
| **字体** | 不在项目里：vite 把 `/fonts/` 映射到 `$OPUS_HOME/_assets/fonts`（`OPUS_ASSETS` 可改） |

## 与原版的差异（改过的地方）
- **渲染脚本**：Bun → Node（`scripts/render.mjs`，WebSocket 用 `ws` 包），内置 WSL2 下调用 NVIDIA 显卡的参数（见 SETUP.md）。全局对象 `window.__pdoom` → `window.__opus`
- **歌曲与歌词可选**：`AudioData.load()` 找不到 `audio.json` 时用 `project.json` 合成恒定节拍网格；`Lyrics.load()` 找不到时返回空（`lyrics.get()` 仍会抛错，场景要歌词行时会大声失败）
- **P(doom) 仪表 → 通用读数** `Readout`：步进值在 `project.json.readout = {label, steps:[[秒,值],…], digits}`；post 参数 `pdoom`/`pdoomText` 改名 `readout`/`readoutText`；`drawReadout(ctx,x,y,v,{caption,max})` 画在场景里
- **中文字体**：`F.hei(weight)` = 思源黑体 300/500/700/900（主声音），`F.song(weight)` = 思源宋体 400/700/900（引文、神圣时刻）；原有 `F.archivo()` / `F.mono()` / `F.serif()` 不变
- **歌词对中文**：`norm()` 保留中日韩字符；`lineCharProgress` 只在真有空格处跳空格
- **预览播放器**：无歌时用 `performance.now()` 计时

`examples/scenes/` 是原版全部场景（只读参考，不参与编译）。里面引用的 `PDoom`/`formatPDoom` 已不存在：抄过来时换成 `Readout` + `project.json.readout`，`window.__pdoom` 换 `__opus`。

## 场景写法要点（详见 docs/upstream/ENGINE.md「Writing a scene」「Toolbox」）
- **确定性**：输出只能是 `f.t` 的纯函数（种子随机 `mulberry32`/`hash`），禁用 `Math.random()`/`Date.now()`。导出时每帧会乱序渲染多个子帧来做运动模糊。按 60fps 闪烁/抖动用 `frameIdx(t)`，不用 `Math.floor(t*60)`
- `render()` 必须完整覆盖 `out`（线性 HDR）；颜色用 palette 常量；> ~0.85 的线性亮度会辉光
- 找歌词按内容：`this.ctx.lyrics.get('某句')`，不写死秒数；拍点用 `f.beat`/`f.beatPhase`/`audio.timeOfBeat(i)`/`audio.hit('kick', t)`
- 每个场景 Canvas2D 层最多 2~3 个（每层每子帧有上传成本，见下）
- 转场默认交叉淡化；硬切 = 时间窗首尾相接；自定义转场设 `handlesTransition = true` 用 `f.under`
- 场景可以返回 post 覆盖：`bloom, halation, ca, grain, vignette, fade, flash, shake, zoom, invert, paper, readout…`
  - ⚠️ `flash` 是线性空间的加性白：残留 0.03~0.04 在屏幕上就是整屏灰底（sRGB 约 50/255）。重击闪白用一帧左右就归零的窗口（`(1 - prog(t, T, T + 0.05))`），别用半衰期 0.08 s 以上的 `pulse`

## 多 agent 分工（原版的做法，用户明确要求多 agent 时才用）
原版由主 agent 统筹、子 agent 各写一个场景：`TREATMENT.md` 分场表有 owner 列；规则是**子 agent 只改自己的 `scenes/<名>.ts` 与 `scenes/<名>-*.ts`，不改 `timeline.ts` 和引擎，要改引擎在最终报告里提给主 agent**；用 `--only <id>` 只加载自己的场景、`stills` 出图后自己 Read 检查。

## 性能参考（2026-09-29 实测，WSL2 + RTX 3050 Laptop 4GB，1080p）
| 项 | 数值 |
|---|---|
| WebGL 设备 | 默认 SwiftShader（CPU）；加 `--use-angle=gl` + `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` → D3D12 上的独显（render.mjs 已内置） |
| 光线步进场景单帧（修格斯） | SwiftShader ~6 s → 独显 ~10–20 ms |
| 模板 demo 每子帧 | ~22 ms（含一个全屏 Canvas2D 文字层；关 2D canvas 加速前 ~45 ms） |
| 导出吞吐 | `--samples 12` ≈ 3.5 帧/s（perf，不含编码）；`--samples auto`（平均 ~40 子帧）≈ 0.5 帧/s（关 2D 加速之前测的，现在应更快） |
| 估算 | 1 分钟 30fps 草稿（samples 4）≈ 5–10 分钟；1 分钟 60fps 自适应成片 ≈ 1–2 小时 |
| 4 万粒子 CPU 算位置 + 投影（21 s 的片子） | 每子帧 ~68 ms；草稿 30fps/samples 4 用 3 分钟；成片 60fps `--samples auto --max-samples 12` 用 9.7 分钟（2.2 帧/s） |
| 2.6 万粒子 + ~1300 条连线（43 s 的片子） | 成片 60fps `--samples auto --max-samples 12` 用 19 分钟（2.3 帧/s） |

⚠️ Canvas2D 层每个子帧都要重新上传纹理（D3D12 通路上这是 demo 里最大的单项开销：关掉 2D canvas 加速前，去掉文字层每子帧省 ~36 ms），文字多、层多的场景成本线性上涨。静止的文字层可以缓存（内容不变就不 `upload()`）。
