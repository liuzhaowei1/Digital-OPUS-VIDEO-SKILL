#!/usr/bin/env bash
# 生图做画面素材（OpenAI 图像接口，默认 gpt-image-2.5-flare，OPUS_IMAGE_MODEL 可改）。不给参考图走 /images/generations；给参考图走 /images/edits（锁角色长相、照着照片画地点）
# Usage: gen_image.sh <prompt_file> <out_png> [size=1536x1024] [quality=medium] [ref1 ref2 ...]
# 撞限流自动重试 6 次；成功打印 "OK <路径> 约 $<估算>"（按脚本内单价估，不是账单数）
set -euo pipefail
PF="$1"; OUT="$2"; SIZE="${3:-1536x1024}"; Q="${4:-medium}"; shift $(( $# < 4 ? $# : 4 ))
# key：环境变量 OPENAI_API_KEY，或 OPUS_IMAGE_KEY_FILE 指向一个只含 key 的文本文件
[ -f "$PF" ] || { echo "prompt file not found: $PF" >&2; exit 1; }
if [ -n "${OPUS_IMAGE_KEY_FILE:-}" ]; then KEY="$(tr -d '[:space:]' < "$OPUS_IMAGE_KEY_FILE")"; else KEY="${OPENAI_API_KEY:-}"; fi
[ -n "$KEY" ] || { echo "no key: set OPENAI_API_KEY or OPUS_IMAGE_KEY_FILE" >&2; exit 1; }
MODEL="${OPUS_IMAGE_MODEL:-gpt-image-2.5-flare}"
mkdir -p "$(dirname "$OUT")"

call() {
  if [ $# -gt 0 ]; then
    local args=(); for r in "$@"; do args+=(-F "image[]=@$r"); done
    curl -s --max-time 280 -X POST https://api.openai.com/v1/images/edits \
      -H "Authorization: Bearer $KEY" \
      -F model="$MODEL" -F "prompt=<$PF" -F size="$SIZE" -F quality="$Q" "${args[@]}"
  else
    python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[4],"prompt":open(sys.argv[1]).read(),"n":1,"size":sys.argv[2],"quality":sys.argv[3]}))' "$PF" "$SIZE" "$Q" "$MODEL" \
    | curl -s --max-time 280 -X POST https://api.openai.com/v1/images/generations \
      -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" --data-binary @-
  fi
}

for i in 1 2 3 4 5 6; do
  if call "$@" | python3 -c '
import sys, json, base64
d = json.load(sys.stdin)
if "error" in d:
    print("API错误:", d["error"]["message"][:300], file=sys.stderr); sys.exit(2 if "Rate limit" in d["error"]["message"] else 1)
open(sys.argv[1], "wb").write(base64.b64decode(d["data"][0]["b64_json"] + "=="))
u = d.get("usage") or {}
print("OK %s 约 $%.3f" % (sys.argv[1], (u.get("input_tokens", 0) * 5 + u.get("output_tokens", 0) * 30) / 1e6))' "$OUT"; then
    exit 0
  else
    rc=$?; [ $rc -eq 2 ] || exit $rc
    sleep $((15 + i * 5))
  fi
done
exit 1
