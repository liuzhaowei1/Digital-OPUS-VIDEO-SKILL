#!/usr/bin/env bash
# New opus-video project. 一部片分两半：
#   交付文件夹：给人看的一切  $OPUS_DELIVER/<YYYY-MM-DD>_<slug>/  根目录只放成片
#       方案/ 静帧/ 草稿/ 素材/ 音频/
#   代码工作区：$OPUS_HOME/<YYYY-MM-DD>_<slug>/   内有 deliver → 交付文件夹 的软链
# 环境变量（都有默认值）：
#   OPUS_HOME      共用环境与代码工作区，默认 ~/opus-video
#   OPUS_DELIVER   交付文件夹的根，默认 $OPUS_HOME/films（WSL 用户可设成 /mnt/c/... 方便在资源管理器里看）
#   OPUS_REMOTION  Remotion 工作区，默认 $OPUS_HOME/remotion-base（由 scripts/setup-remotion.sh 建）
# 用法：
#   bash scripts/new-project.sh <slug>             # 内置引擎：复制模板 + npm install + git init
#   bash scripts/new-project.sh <slug> --remotion  # Remotion：代码写在 Remotion 工作区，工作区只放音频分析数据
set -euo pipefail
SLUG="${1:?usage: new-project.sh <slug> [--remotion]}"
MODE="${2:-engine}"
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
OPUS_HOME="${OPUS_HOME:-$HOME/opus-video}"
OPUS_DELIVER="${OPUS_DELIVER:-$OPUS_HOME/films}"
OPUS_REMOTION="${OPUS_REMOTION:-$OPUS_HOME/remotion-base}"
NAME="$(date +%F)_$SLUG"
DEST="$OPUS_HOME/$NAME"
DELIVER="$OPUS_DELIVER/$NAME"
for p in "$DEST" "$DELIVER"; do [ -e "$p" ] && { echo "exists: $p" >&2; exit 1; }; done
[ -d "$OPUS_HOME/_assets/fonts" ] || { echo "fonts missing: $OPUS_HOME/_assets/fonts (see docs/SETUP.md)" >&2; exit 1; }
if [ "$MODE" = "--remotion" ] && [ ! -d "$OPUS_REMOTION" ]; then
  echo "Remotion workspace missing: $OPUS_REMOTION (run scripts/setup-remotion.sh)" >&2; exit 1
fi

mkdir -p "$DELIVER"/{方案,静帧,草稿,素材,音频} "$DEST"
if [ "$MODE" = "--remotion" ]; then
  mkdir -p "$DEST/public" "$OPUS_REMOTION/public/$SLUG" "$OPUS_REMOTION/src/compositions/$SLUG"
  CODE="$OPUS_REMOTION/src/compositions/$SLUG/（素材 $OPUS_REMOTION/public/$SLUG/）；音频分析数据 $DEST/public/"
else
  cp -r "$SKILL/engine/." "$DEST/"
  rm -rf "$DEST/examples" "$DEST/node_modules" "$DEST/out"   # examples stay in the skill (read them there)
  CODE="$DEST/"
fi
ln -s "$DELIVER" "$DEST/deliver"
cat > "$DELIVER/方案/README.md" <<EOF
# $NAME

- 成片：上一级根目录的 \`$NAME.mp4\`
- 代码：$CODE
- 子文件夹：方案（方案书、台本、交接）/ 静帧（自查截图、拼板）/ 草稿（草稿视频、被替换的旧版本）/ 素材（生图、抠图、参考图）/ 音频（BGM、旁白、cues.json 副本）
EOF
if [ "$MODE" != "--remotion" ]; then
  cd "$DEST"
  printf 'node_modules/\nout/\ndeliver\n' > .gitignore
  npm install --no-audit --no-fund --silent
  git init -q && git add -A && git commit -qm "new project from opus-video engine template" || true
fi
echo "$DEST"
echo "$DELIVER"
