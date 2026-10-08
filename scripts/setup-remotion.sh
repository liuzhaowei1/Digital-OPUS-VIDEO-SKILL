#!/usr/bin/env bash
# 建 Remotion 工作区：复制 skill 的 remotion/ 模板 → $OPUS_REMOTION，装依赖，拷旁白模板要用的中文字体。
#   OPUS_HOME 默认 ~/opus-video；OPUS_REMOTION 默认 $OPUS_HOME/remotion-base
# 验证：cd $OPUS_REMOTION && npx remotion still NarrationDemo out/demo.png --frame=150
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
OPUS_HOME="${OPUS_HOME:-$HOME/opus-video}"
OPUS_REMOTION="${OPUS_REMOTION:-$OPUS_HOME/remotion-base}"
[ -e "$OPUS_REMOTION" ] && { echo "exists: $OPUS_REMOTION" >&2; exit 1; }
FONTS="$OPUS_HOME/_assets/fonts"
for f in NotoSansSC-500.ttf NotoSansSC-700.ttf; do
  [ -f "$FONTS/$f" ] || { echo "font missing: $FONTS/$f (see docs/SETUP.md 字体)" >&2; exit 1; }
done
mkdir -p "$(dirname "$OPUS_REMOTION")"
cp -r "$SKILL/remotion" "$OPUS_REMOTION"
mkdir -p "$OPUS_REMOTION/public/narration"
cp "$FONTS/NotoSansSC-500.ttf" "$FONTS/NotoSansSC-700.ttf" "$OPUS_REMOTION/public/narration/"
cd "$OPUS_REMOTION"
npm install --no-audit --no-fund --silent
npx remotion browser ensure
echo "$OPUS_REMOTION"
