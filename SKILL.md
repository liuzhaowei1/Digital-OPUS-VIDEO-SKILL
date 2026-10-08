---
name: opus-video
description: This skill should be used whenever the user wants Claude to MAKE a video with code or other non-video-generation means (Remotion, three.js/WebGL, SVG, Blender, ffmpeg…; image models may supply still assets such as Q-version characters or scenes) — e.g. "/opus-video", "创建一个XXX风格的视频", "做一个《某某》风格的视频", "参考这个视频的风格做一个", "照着 <文件/项目> 的风格做视频", "用 remotion 做个视频", "做个动效/motion graphics", "把这个画成动画视频", "做个数据展示/图表动画/logo 动画/倒计时视频", "按这段配音/旁白做个视频", "我录了音，帮我配画面", "做个口播讲解视频", "用这些照片做个生日视频", "拆一下这个视频的风格". Sound drives the picture three ways — from a song, from a voiceover/narration, or synthesized together with the picture. Two lanes — a quick lane for one-line animations with no reference or aesthetic stakes (brief plan → still → render), and a full lane for reference-style, material-based or aesthetics-driven videos (break down the reference, decompose intent, ask only the necessary questions, treatment + style bible, stills, sample, build, self-review). Not for end-to-end text-to-video generation models or editing real footage.
version: 1.5.0-oss
---

# /opus-video — 代码做视频

用代码或其他非视频生成模型的方式做视频，都走本 skill；文生视频/图生视频模型（Seedance 一类）不用。判据、视频类型表、已知短板在 `docs/TYPES.md`。分两档：

| 档 | 什么时候 | 流程 |
|---|---|---|
| **快速档** | 一句话的动效/数据图表/文字/logo/倒计时，没给参考和素材、用户没表现出在意审美，时长 ≤ 约 30 秒 | 一两句话复述视觉方案（元素、时长、配色、时序）→ 有歧义或几种明显不同走法时 AskUserQuestion 让用户选，否则合理默认 → 出一张代表静帧自检后发用户 → 渲整片 → 回报路径。不写方案书、不问相似度；默认静音，用户给了音频就用，要声音但没给就用网格合成 BGM |
| **完整档** | 给了参考或素材（参考片、风格库片名、文件、项目、照片、配音）、说了"XX 风格"、要配乐卡拍、讲一个完整主题、或用户强调审美 | 下面 Step 1–7 |

拿不准归哪档时按完整档的 Step 2 拆意图，缺的只有规格类信息就降为快速档。快速档中途用户开始提风格要求 → 升完整档，补方案书。

## 已定的原则
0. **按内容设计，现有的都是起点**：类型（`docs/TYPES.md` 类型表）给结构的起点，手法（`docs/CRAFT.md` 手法库）按这条内容挑、可跨类型组合，风格来自参考或提案，工具按内容选。四样都在持续扩充，现有的不是全集，刚收录的也不是新模板；内容需要而库里没有的，提出来。用户每一次反馈只对它针对的那类内容生效，不外推成通则（`docs/TYPES.md`「方法观」）
1. **工具不限代码**：类型表的「常用栈」是起点；内容适合代码的纯代码做，碰到代码短板再引入别的工具，可混用。不默认 Remotion。完整档选型写进方案书由用户拍板，快速档自选、复述方案时说一句：
   - **内置引擎**（本 skill `engine/`，three.js 逐帧确定性渲染）：着色器质感、光线步进 3D、高品质排版、严格卡拍、真运动模糊、4K。用法 `docs/ENGINE-GUIDE.md`
   - **Remotion**（工作区 `$OPUS_REMOTION`，`scripts/setup-remotion.sh` 建）：DOM/CSS/SVG 动效、数据图表、文字动效、图片素材动画。写 composition 前读 `docs/REMOTION.md`
   - **生图模型出静态素材**（角色、场景、道具），再由上面两者动起来：`docs/ASSETS.md`
   - Blender（需用户自己装，可经 Blender MCP 驱动）：需要真实肢体表演、骨骼/IK 时考虑；照片级写实（物理材质、全局光、真景深，如《拓扑优化》）也考虑。本 skill 未验证这条路的角色动画、渲染速度和质感，用前先试渲一个镜头
   - ffmpeg 滤镜、Canvas 等按需
2. **和参考像到什么程度，每次问**：照搬风格换内容、借骨架做差异、只取手法，都是正当需求。
3. **声音单独决策，来源每次问**。三条路，命令在 Step 6，精度与判据在 `docs/AUDIO.md`：
   - **按歌做画面**（现成曲目或 AI 音乐模型生成，由用户提供）：先有音乐再做画面；MV 必须走这条
   - **按旁白做画面**（用户自录，或用 TTS 合成 `scripts/tts.py`）：先有人声再做画面，技术上复用按歌那条的分离与对齐，台本当歌词
   - **画面和声音一起做**：网格合成 BGM，声画读同一份 `cues.json`；旁白片要底乐时也可垫在人声下

## 环境变量
| 变量 | 默认 | 放什么 |
|---|---|---|
| `OPUS_HOME` | `~/opus-video` | 共用环境（`_assets` 字体、`_venv`、`_models`、`_refs`）与各片代码工作区 |
| `OPUS_DELIVER` | `$OPUS_HOME/films` | 各片交付文件夹的根 |
| `OPUS_LIBRARY` | `$OPUS_HOME/library` | 风格库：拆过的参考片分析 md |
| `OPUS_REMOTION` | `$OPUS_HOME/remotion-base` | Remotion 工作区 |

下文命令里的 `<skill>` 指本 skill 目录。安装与自检见 `docs/SETUP.md`；首次使用前确认需要的组件已装，缺什么告诉用户装什么，不自行降级。

## 工作流

### Step 1 — 盘点输入
用户给的东西分三类，可以同时有：

| 输入 | 怎么处理 |
|---|---|
| **风格参考**：风格库片名（"AI简史风格"） | `ls "$OPUS_LIBRARY"` 模糊匹配，多个命中列出来问；读 `<片名>.md` 的「风格分析」「复用指南」全文 → 「代表帧」开 3~6 张原图 → 同文件夹有 `风格圣经-*.md` 就通读（比读图反推准） |
| 风格参考：**一部还没拆过的视频**（本地文件或链接） | 按 `docs/REFERENCE.md` 拆：`ref_frames.py` 抽帧 → 读拼板 → 写分析 md 存进风格库。拆完再回到这里按"风格库片名"那一行读。只想一次性参考、不想存的，也至少抽帧读拼板 |
| 风格参考：md、图片 | 直接读 |
| 风格参考：Skillry 案例 / awesome-opus5-5-videos 条目 | `python3 <skill>/scripts/skillry_ref.py <链接> [--x]` → `$OPUS_HOME/_refs/clips/<slug>/`。先读拼板再读 `prompt.md`。⚠️ **提示词≠风格**：画面常来自原作者没公开的设计稿，风格以画面为准；小字看不清加 `--x` 取 X 原画质（需能访问 X）；`remake.mp4` 是 Skillry 重做版，不是原作 |
| 风格参考：视频项目（本机目录、git 仓库） | README、docs（分镜/风格说明）、色板/字体常量、场景源码结构；能跑就出几张静帧看 |
| **自带素材**：照片、配音/旁白、歌曲、台本 | 照片 → 决定画面素材来源（`docs/ASSETS.md`），默认只做生图参考、不直接进画面；音频 → 定声音那条路（原则 3）；台本 → 旁白片的分场骨架 |
| **只有想法**（"给女朋友做个生日视频""按这段话做个视频"） | 没有风格参考时，风格由 Claude 在方案书里发散提案（2~3 个方向各一段话让用户挑），不空手问"你想要什么风格" |

用户只说类型、没点名片子（"做个像那几部 MV 一样的"）：`grep -H "^- 类型" "$OPUS_LIBRARY"/*/*.md` 列出同类片子让用户挑；风格库还空时，按 `docs/TYPES.md` 该类型「已见过的做法」描述给用户，并指 `docs/REFERENCES.md` 里的原片链接。

读完输出**参考摘要**（给自己用，不必全贴给用户）：色板、字体、材质、运动与转场、节奏、叙事手法、音画关系、技术路线、标志性元素（一眼认出出处的东西）。

### Step 2 — 拆意图、定类型
先按 `docs/TYPES.md`「视频类型」表定类型（先看什么决定结构，再看画面语法）：类型给起点，表里「已见过的做法」是参照不是规定。**都对不上时停下问用户是否新增类型**。再按这条内容从 `docs/CRAFT.md` 手法库挑手法，跨类型借用正常。然后把用户这句话拆成下表，每格标"已知 / 可默认 / 必须问"：

| 维度 | 内容 | 默认值 |
|---|---|---|
| 内容 | 讲什么、给谁看、核心信息几条 | 无，缺了必须问 |
| 借哪几层 | 画面语言（色板/字体/材质）、运动与节奏、叙事手法、音画关系、技术路线 | 全借 |
| 相似度 | 照搬风格换内容 / 借骨架做差异 / 只取一两个手法 | 有风格参考时必须问 |
| 时长 | 按信息量估：一个概念 ≈ 8~15 秒讲清。信息量和时长不匹配时指出来 | 按信息量估 |
| 声音 | 用户给曲目 / 用户用 AI 音乐模型生成后给我 / 用户给旁白配音 / 我用 TTS 合成旁白（台本审过再合成，音色 `--list-voices` 让用户选） / 我网格合成 BGM / 静音 | 必须问；讲解类推荐旁白；短片、宣传片、动效没给歌时推荐网格合成 |
| 画面素材 | 代码画 / 生图整幅场景 / 生图角色抠图 + 场景 / 用户照片转生图（`docs/ASSETS.md`） | 按类型表常用栈提案；要花生图费用时写进方案书让用户拍板 |
| 规格 | 画幅、分辨率、帧率、用途（B 站、竖屏、演示） | 16:9、1920×1080、30fps |

### Step 3 — 提问（只问"必须问"的）
- 一次问完，用 AskUserQuestion，最多 4 题；每题给选项、推荐项放第一个并写理由
- 用户这句话已经说清的不问；自己能查到的不问
- 典型必问：相似度（有参考时）、声音来源；内容没给时问内容；时长明显不够时问时长
- 不问：创意概念、贯穿线、手法、叙事结构、转场，由 Claude 在方案书里提案

### Step 4 — 方案书（拍板前不写代码）
先 `bash <skill>/scripts/new-project.sh <slug>`（Remotion 片加 `--remotion`）建项目，方案书写到交付文件夹 `方案/TREATMENT.md`（目录约定见「项目文件放哪」）。结构与写法见 `docs/CRAFT.md`「方案书结构」，完整实例是 `docs/upstream/TREATMENT.md`：
1. **一段话创意**：讲什么、用什么方式讲、贯穿线
2. **风格圣经**：色板（hex）、字体（各自角色）、材质与后期、运动规则（缓动、卡拍）、转场规则、**负面清单**（按本片风格写）。借骨架时写明"换掉参考的哪些标志性元素、换成什么"
3. **选用的手法**：每条一句"为什么适合这条内容"，说不出理由就不用
4. **分场表**：时间窗、内容/台词、画面、转场、对应音乐段落。有角色动作的镜头加一列「表演难度与藏法」：情绪交给脸和符号、难动作拉远/遮挡/用速度糊过去、近景少动（判据见 `docs/TYPES.md`「已知短板」）。每镜必有一列「实现依赖」，三态择一：**已有**（指到具体工具/文件，如 `spacetime-lens.ts`）/ **需新装**（装什么、装哪、工作量）/ **做不到**（改成什么替代画法）。判据是实查（`ls`/`grep` 引擎、Remotion 工作区、`$OPUS_HOME/_assets`），不凭印象标"已有"
5. **技术选型与画面素材**：用什么栈、素材从哪来、为什么、本机能不能跑、渲染耗时和生图费用估计。分场表里所有「需新装」「做不到」汇总成一张清单放这里，随方案一起拍板：装还是绕在此定，不留到制作中途。制作中才发现缺能力 → 停下带选项问，不自行凑合或降级
6. **声音方案**：有歌写来源和分析计划；有旁白时分场表就是台本，每段写转场、画面内容、字幕、配音语气四项，**台本经用户审过再录音**；网格合成写 BPM、段落和弦走向、鼓的密度曲线、上扬、抽空、重击的位置

把要点（不是全文）贴给用户拍板。文字方案书对用户缺画面感，拍板时配静帧或样片，别只让用户读文字想象画面。用户改方向就改方案书，不带着旧方案往下做。

### Step 5 — 静帧与样片确认
- 每个场景出 1 张代表帧，拼成一张总览（contact sheet；内置引擎用 `node scripts/render.mjs sheet --times …`）。先自己检查：风格圣经里的色板、字体、负面清单逐条对；再发给用户确认。**静帧不过不渲整片**
- 要生图素材的片子，先定角色设定图并给用户审，再出其余素材
- **长片或要花钱的片子，先做十几秒到 40 秒的样片**（开头一段或最能代表风格的一段）给用户看，认可后再铺全片

### Step 6 — 制作
开工前读 `docs/AUDIO.md`（有声音时）和 `docs/ASSETS.md`（有生图素材时）。

- **按歌做画面**：
  ```bash
  cd <skill>/analysis && PY=$OPUS_HOME/_venv/bin/python
  $PY separate.py <项目目录> <歌曲文件>            # 无损解码 + Demucs 分轨（有 GPU 用 GPU）
  $PY analyze_audio.py <项目目录> [--bpm 132]      # 节拍/小节/段落/包络/鼓与人声起音 → audio.json
  $PY align_lyrics.py <项目目录> --lyrics 歌词.txt [--windows w.json]  # 逐词对齐 → lyrics.json（无歌词文本时 --whisper 先转写）
  ```
  分析产物进项目 `public/data/`；歌曲同时拷进项目 `public/audio/`，`project.json` 写 `"audio": "audio/<文件名>"`。对齐结果按 AUDIO.md 的精度预期逐行核对
- **按旁白做画面**：同上三条命令，台本当歌词（一行一句）。没有录音、要我配音时先合成：
  ```bash
  python3 <skill>/scripts/tts.py 台本.txt --out-dir <交付文件夹>/音频/旁白 --voice Cherry   # 系统 python3 + dashscope，不用 _venv
  ```
  产出 `narration.wav`（整轨，拿去 `separate.py`）、`narration.json`（逐句起止秒数，只按句切镜时不用再对齐）、`script.txt` + `windows.json`（给 `align_lyrics.py --lyrics … --windows …` 做逐字对齐）。画法按方案书定的手法；要逐句演角色时，现成的角色与镜头模板在 Remotion 工作区 `src/compositions/narration/`（`Chars.tsx` 角色与道具、`kit.tsx` 的 `G()` 配置化镜头和 `wt()` 按字取时间），最小示例 `NarrationDemo.tsx`
- **网格合成 BGM**：先读 AUDIO.md「配乐方法」（创意参考，不是硬性规则，有更好的路子提出来）→ 从场景代码列画面动作时刻表 → 写 `make_cues.py` 生成 `cues.json`（节奏走拍、同期声走秒，默认真实乐器 `voices` + 同期声 `events`）→ `timeline.ts` 从它读切点 → `$PY synth_bgm.py <项目目录> [--stems]` → `$PY analyze_ref_audio.py <bgm.wav> --cues <项目>/cues.json` + 断点扫描验收 → 带画面小样给用户听
- **生图素材**：`scripts/gen_image.sh` 出图（带参考图即锁定角色长相）→ 要叠加的角色用 `scripts/cutout.py` 抠图 → 原图和抠图存交付文件夹 `素材/`，工作副本放进 Remotion `public/<slug>/` 或引擎项目 `public/`
- 每个场景做完出几张静帧或短片段自查，不等全片做完才看
- **有角色动作或逐帧滤镜（油画类、笔触类）的场景，静帧之外渲 3~5 秒短片段发用户看**：脚打滑、节奏僵、相邻帧笔触闪烁在静帧里看不出，这类验收靠用户
- 画面里的文字、数字以方案书为准，不临时编

### Step 7 — 渲染、自评、交付
- 成片落交付文件夹根目录 `<YYYY-MM-DD>_<slug>.mp4`；改版时旧成片移进 `草稿/` 并加 `_v1` 后缀，根目录永远只有一个最新版。内置引擎：草稿 `video --samples 4 --fps 30`，成片 `video --samples auto --shutter 0.2`（耗时见 ENGINE-GUIDE 性能表，长片先估时告诉用户）
- 抽帧自己看一遍，**按风格圣经逐条自评**：哪些做到了、哪些没做到、和参考的差距在哪。如实写，不夸
- 交付后清理：删代码工作区 `out/` 里的草稿和成片副本（成片已在交付文件夹）；音频定稿副本拷进 `音频/`
- 交付时说明：成片路径、方案书路径、自评、已知不足、花费（生图、TTS）、需要用户接手的（如需要人声的配乐）

## 成本与上下文
- **读图一律先拼板**：多帧自查拼成一张低清拼板（每格 ≤640 宽）一次 Read，不逐帧 Read 原图；只有看小字、细节时才开原图局部。抽帧命令逐张写输出（`for s in …; do ffmpeg -ss $s -i <mp4> -frames:v 1 …; done`），一条 ffmpeg 挂多个 `-ss -i` 输入时不指定映射只会重复取第一个输入
- **会话变重就交接**：单会话读图累计几十张、或全片级制作跨多轮时，把进度写进交付文件夹 `方案/HANDOFF.md`（已定方案、已完成、下一步、文件位置），建议用户开新会话接着做。实例：一个旁白全片会话读了 52 张图、上下文约 41 万 token 后，请求无响应卡死
- 生图、TTS 按量计费，先样片后全片（Step 5）；重生前先说明原因

## 项目文件放哪
一部片 = 一个交付文件夹，用户打开就能看到这部片的全部经过、能整个分享或删除；代码和共用环境另放。

| 位置 | 放什么 |
|---|---|
| `$OPUS_DELIVER/<YYYY-MM-DD>_<slug>/` | 根目录只放成片 mp4；`方案/`（方案书、台本、HANDOFF、代码位置 README）`静帧/`（自查截图、拼板、给用户确认的图）`草稿/`（草稿视频、被替换的旧成片）`素材/`（生图、抠图、参考照片）`音频/`（BGM、旁白、cues.json 的定稿副本） |
| `$OPUS_HOME/<YYYY-MM-DD>_<slug>/` | 代码工作区：引擎源码、node_modules、渲染读的 public/（音频、分析数据）、out/ 临时输出；`deliver` 软链到交付文件夹 |
| `$OPUS_REMOTION/src/compositions/<slug>/`、`public/<slug>/` | Remotion 片的代码与画面素材（渲染要从这里读） |
| `$OPUS_HOME/_assets` `_venv` `_models` `_refs`、`$OPUS_REMOTION`、`$OPUS_LIBRARY` | 各片共用，不属于哪部片 |

- 凡是给用户看、或以后回看有用的产物（静帧、拼板、草稿、生图）**直接写进交付文件夹**的对应子目录，不写到 `$OPUS_DELIVER` 根下，也不留在代码工作区
- 方案书只存交付文件夹一份，不在代码工作区放副本
- 素材要被渲染读取的（生图、音频），工作副本在代码工作区，交付文件夹放同一份的副本

## 写方案书估可行性时要知道的
- 内置引擎靠 WebGL：先 `node scripts/render.mjs gpu` 确认用上了显卡（`docs/SETUP.md`「GPU 自检」）；落到 SwiftShader 时光线步进类场景慢几百倍，方案书里要据此估渲染时间或改画法
- Remotion 是 Chrome 逐帧光栅化，硬件编码器只加速编码段，不缩短整体渲染时间
- 性能参考数据（一台 WSL2 + 4GB 显存笔记本的实测）在 `docs/ENGINE-GUIDE.md`

## 注意
- 风格库 md 里「标志性元素」是否保留由相似度决定，不是禁用清单
- 版权：内置引擎源自 pdoom-video（MIT），`engine/LICENSE` 与 `NOTICE.md` 随项目复制，不要删；歌曲、字体按各自许可；拆参考片只做本地分析，下载的视频和截图不再发布；用别人视频的音频做的测试片只在本地用
- 通用工艺（方案书结构、运动、排版、文字与声音同步）和手法库见 `docs/CRAFT.md`，写方案书前读；某部参考片自己的语气和负面清单在它的风格库 md 或风格圣经里，不当通用规则
