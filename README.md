# /opus-video：让 Claude 写代码做视频

一个给 [Claude Code](https://claude.com/claude-code) 用的 skill。说一句"照这部片子的风格，讲我的题目"，或者只说你想讲什么，Claude 会拆参考片、定类型、只问必须问的问题、写方案书、出静帧和样片，最后用代码逐帧渲染出成片。

它不调用视频生成模型。画面是 Claude 写的 three.js / Remotion / SVG 代码一帧一帧算出来的，声音可以跟着歌、跟着旁白，也可以由代码和画面一起合成。

---

## 它解决什么问题

最近网上有大量"Opus 5.5 写代码做的视频"。照着别人公开的提示词跑一遍，通常复刻不出来：

1. **风格不在提示词里。** 收录这类作品的 awesome-opus5-5-videos 仓库，513 条里有 234 条标注作者只公开了部分提示词；还有作者的提示词是"照着附上的 Figma 设计稿做"
2. **一句话的提示词没有结构。** 片子该按歌走、按旁白走、按知识点走，还是按一个问题走，决定了整部片子的骨架
3. **代码有短板。** 角色肢体表演、逐帧滤镜闪烁，照普通动画剧本写基本演不出来

这个 skill 把 28 部片子逐帧拆解后的结论写成了流程：

| 组成 | 内容 | 位置 |
|---|---|---|
| 视频类型表 | 按"什么决定结构"分出 11 类，每类给判据、见过的做法、常用技术栈 | `docs/TYPES.md` |
| 手法库 | 37 条手法，分贯穿线、概念变画面、结构骨架、节奏与文字四组，每条写明适合什么、不适合什么、出自哪部片子 | `docs/CRAFT.md` |
| 拆参考片 | 按画面变化抽关键帧、出编号拼板，按模板写风格分析，存进你自己的风格库 | `docs/REFERENCE.md`、`scripts/ref_frames.py` |
| 声音 | 按歌（分轨、节拍、逐词对齐）、按旁白（TTS + 对齐）、代码合成 BGM（声画读同一张时间表） | `docs/AUDIO.md`、`analysis/` |
| 画面素材 | 代码画 / 生图出静态素材 / 用户照片转插画，角色一致性做法 | `docs/ASSETS.md` |
| 渲染 | 内置 three.js 逐帧确定性引擎（改自 pdoom-video）+ Remotion 模板 | `engine/`、`remotion/` |

---

## 它怎么带你做

**有参考片时：**
1. 拆参考片：抽帧、读拼板，写出色板、字体、运动、转场、节奏、标志性元素
2. 定类型，把需求拆成内容、借哪几层、相似度、时长、声音、画面素材、规格七个维度，每格标"已知 / 可默认 / 必须问"
3. 只问必须问的，最多四题。最关键的是**相似度**：照搬风格换内容、借骨架做差异，还是只取一两个手法
4. 写方案书和风格圣经（色板到 hex、字体角色、负面清单），分场表每一镜标"已有 / 需新装 / 做不到"
5. 静帧总览 → 样片 → 全片，静帧不过不渲全片
6. 按风格圣经逐条自评

**没有参考片时：** 必须由你回答的只有"讲什么"和"声音从哪来"。创意、贯穿线、手法、叙事结构由 Claude 在方案书里提 2~3 个方向，你挑一个。

**一句话的小动效**（logo 动画、数据图表、倒计时）走快速档：复述方案 → 一张静帧 → 直接渲染。

---

## 安装

### 1. 装 skill 本体

```bash
git clone https://github.com/liuzhaowei1/Digital-OPUS-VIDEO-SKILL.git ~/.claude/skills/opus-video
```

### 2. 装运行环境（按需）

所有共用组件放在 `$OPUS_HOME`（默认 `~/opus-video`），详细命令见 [`docs/SETUP.md`](docs/SETUP.md)：

| 想做什么 | 需要装 |
|---|---|
| 任何片子 | Node.js ≥ 20、ffmpeg、字体（`docs/SETUP.md`「字体」） |
| DOM/SVG 动效、数据图表、旁白插画 | Remotion 工作区：`bash ~/.claude/skills/opus-video/scripts/setup-remotion.sh` |
| 着色器、粒子、3D、严格卡拍 | Chromium：`npx playwright-core install chromium`；有独立显卡更好 |
| 按歌/按旁白卡拍、合成 BGM、拆参考片 | Python 分析环境（torch、demucs、librosa…），首次运行会下载约 1.6 GB 模型 |
| 生图出素材 | 环境变量 `OPENAI_API_KEY` |
| TTS 配旁白 | 环境变量 `DASHSCOPE_API_KEY`（阿里云百炼）+ `pip install dashscope` |

不用一次装齐。缺了哪样，skill 在方案阶段会告诉你装什么。

### 3. 可选的环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `OPUS_HOME` | `~/opus-video` | 共用环境与各片代码工作区 |
| `OPUS_DELIVER` | `$OPUS_HOME/films` | 成片与过程产物（一部片一个文件夹）。WSL 用户可设成 `/mnt/c/...` 在资源管理器里看 |
| `OPUS_LIBRARY` | `$OPUS_HOME/library` | 风格库：拆过的参考片 |
| `OPUS_REMOTION` | `$OPUS_HOME/remotion-base` | Remotion 工作区 |

---

## 用法

```
/opus-video 参考 ~/Downloads/某部片子.mp4 的风格，做一条 1 分钟讲大模型推理的视频
/opus-video 做一个 15 秒的 logo 动画，品牌名叫 Lumen
按这段旁白做个视频：~/录音/intro.m4a
用这些照片给我爸做个生日视频
```

不用斜杠命令，直接说"做一个 XX 风格的视频""用 remotion 做个动效""拆一下这个视频的风格"也会触发。

---

## 不适合的场景

- **剪辑实拍素材**：它生成画面，不是剪辑软件（短视频花字包装除外）
- **需要细腻肢体表演的角色动画**：代码在这件事上有结构性短板，剧本要按"代码能演什么"来写
- **文生视频**：Seedance 一类视频生成模型是另一条路，这里不调用

已验证的平台是 **WSL2 + NVIDIA 显卡**。内置引擎的 GPU 参数在其他平台未实测，自检方法和退路见 `docs/SETUP.md`「GPU 自检」。

---

## 出处与致谢

- 内置引擎改自 [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video)（MIT，作者 Giacomo Magnanini），也就是《I'm Upping My P(doom)》那部 MV 的源码。原许可保留在 `engine/LICENSE`，改动列在 `engine/NOTICE.md`，原版文档逐字保存在 `docs/upstream/`
- 类型表和手法库里引用的 28 部片子，原片链接与作者见 [`docs/REFERENCES.md`](docs/REFERENCES.md)。本仓库不包含这些视频及其截图
- 参考案例库 [awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos)

---

## License

[MIT](LICENSE)（`engine/` 另见 `engine/LICENSE`）
