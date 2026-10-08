# Remotion 路线（DOM/CSS/SVG 动效、数据图表、快速出片）

何时选 Remotion、何时选内置引擎见 SKILL.md「已定的原则」第 1 条。

## 环境
- 工作区：`$OPUS_REMOTION`（默认 `$OPUS_HOME/remotion-base`），由 `scripts/setup-remotion.sh` 从本 skill 的 `remotion/` 模板建（Remotion 4.x，含旁白插画模板 `src/compositions/narration/` 与示例 `NarrationDemo`）。composition 写在 `src/compositions/<PascalName>.tsx`，在 `src/Root.tsx` 注册；静态资源放 `public/`，用 `staticFile('name.png')` 引用
- 模板装的包：`remotion` `@remotion/cli` `@remotion/renderer`；**`@remotion/three` 未装**，要在 Remotion 里用 three.js 时先 `npm i @remotion/three three`（版本与 remotion 对齐）。重 3D、着色器优先走内置引擎
- 建项目 `bash scripts/new-project.sh <slug> --remotion`：composition 写在 `src/compositions/<slug>/`，素材放 `public/<slug>/`（`staticFile('<slug>/x.png')`）。成片、静帧、草稿写交付文件夹 `$OPUS_DELIVER/<YYYY-MM-DD>_<slug>/`（约定见 SKILL.md「项目文件放哪」）
- **GPU**：有硬件编码器时渲染加 `--hardware-acceleration=if-possible`。**NVENC 只加速编码段、省 CPU，不缩短墙上时间**（1080p/20s：CPU 软编 27.7 s vs NVENC 27.2 s，CPU 时间砍 2/3）；瓶颈是 Chrome 逐帧光栅化。别向用户承诺"GPU 让渲染更快"
- `npx remotion gpu` 报 `chrome://gpu` `net::ERR_FAILED` 是 WSL2 headless 已知现象，不影响渲染
- 显存小（4GB 级）时：单路 1080p 没问题，别同时起多路高分辨率渲染
- 工作区损坏时：删掉后重跑 `scripts/setup-remotion.sh`。`src/Root.tsx` 为空时 `npx remotion compositions` 报 `Error: Array of 0 length`，属正常，注册一个 composition 即可

## 写法规则
- `useCurrentFrame()` 取帧、`useVideoConfig()` 取 fps/宽高/时长
- 动画用 `interpolate(frame, [起,止], [值1,值2], {extrapolateLeft:'clamp', extrapolateRight:'clamp'})`；要弹性才用 `spring({frame, fps, config})`
- `<AbsoluteFill>` 做全屏层，`<Sequence from durationInFrames>` 分段，`<Series>` 顺序拼接
- 媒体用 `<Img> <Audio> <Video> <OffthreadVideo>`，不用原生标签
- 优先 `transform: translate/scale/rotate`，不改布局属性；box-shadow、渐变、blur、drop-shadow 可放心用
- ⚠️ **一切动画只由帧号算出**（官方 /docs/flickering："animations run purely off the value of `useCurrentFrame()`"；并行渲染时各标签页不共享状态，不能假设帧按顺序渲染）。所以：
  - 不用 CSS `animation`/`transition`，**不用 SVG 原生动画**（`<animate>` `<animateTransform>`，跑在浏览器时钟上）——关键帧自己用 `interpolate` 算成 transform
  - 不用 `Math.random()`/`Date.now()`，随机用 Remotion 的 `random(seed)`；组件不发网络请求
- 手绘风：rough.js 只给手绘质感；"一笔一笔画出来"用 `stroke-dasharray` + 由帧号算的 `stroke-dashoffset`；轻微抖动用 SVG 滤镜（feTurbulence + feDisplacementMap）且 seed 按帧取整变化
- 2D 角色（代码画；生图素材见 `ASSETS.md`）：SVG 按部件分组成树（身体→四肢→五官），每组的 transform 由帧号驱动；缩放/旋转要设 `transform-origin`（或 `transform-box: fill-box`），否则绕画布原点转
  - ⚠️ 用 `scale(-1,1)` 翻转角色后，身体局部的左臂到了画面右侧：让角色把手伸向对方时要抬另一只手，否则伸手方向背对对方
  - 镜头内的动作点卡在旁白具体的字上时，别卡在句尾的词：镜头在句尾就切走了，动作来不及演完

## 命令
```bash
cd $OPUS_REMOTION
# 静帧（出整片前先看）
D=$OPUS_DELIVER/<YYYY-MM-DD>_<slug>
npx remotion still <ComposId> $D/静帧/f<N>.png --frame=<N> --log=error
# 整片
npx remotion render <ComposId> $D/<YYYY-MM-DD>_<slug>.mp4 \
  --hardware-acceleration=if-possible --codec=h264 --log=error
# 只渲前 1 秒试效果：加 --frames=0-29
```
边调边看：`npm run dev` 起 Studio（localhost:3000），默认不起。
