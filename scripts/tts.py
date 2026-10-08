#!/usr/bin/env python3
"""旁白 TTS：台本逐句合成 → 去首尾静音 → 按停顿拼接，输出整轨与逐句时间表。

走阿里云百炼（DashScope）Qwen-TTS 家族。需要 `pip install dashscope`（系统 python3 即可，不必用分析环境）。
key：环境变量 DASHSCOPE_API_KEY，或 --key-file 指向一个只含 key 的文本文件。

台本格式（一行一句，与 align_lyrics.py 的歌词格式相同）：
  - 空行 = 段落停顿（--para-gap），普通换行 = 句间停顿（--gap）
  - 以 # 开头的行跳过（可写注释）
  - 数字-数字（7-11）会被读成"七减十一"，脚本会报警，台本里改写成"七杠十一""七到十一"

输出（--out-dir）：
  lines/<序号>_<hash>.wav   逐句原始合成（按 文本+模型+音色 缓存，重跑不重复扣额度）
  narration.wav             整轨（24 kHz 单声道）
  narration.json            [{i, text, start, end}] 逐句起止秒数（整轨时间）
  script.txt                去掉空行和注释后的台本，可直接喂 align_lyrics.py 做逐字对齐
  windows.json              逐句时间窗，给 align_lyrics.py --windows

用法：
  python3 tts.py 台本.txt --out-dir 音频/旁白 [--voice Cherry] [--key-file ~/.dashscope-key] [--model qwen-tts-latest]
  python3 tts.py --list-voices
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MODELS = ('qwen-tts', 'qwen-tts-latest', 'qwen-tts-2025-05-22', 'qwen-tts-2025-04-10')
VOICES = {
    'Cherry': '芊悦 女 阳光亲切', 'Serena': '苏瑶 女 温柔', 'Ethan': '晨煦 男 温暖有活力',
    'Chelsie': '千雪 女 二次元', 'Dylan': '晓东 男 北京话', 'Jada': '阿珍 女 上海话', 'Sunny': '晴儿 女 四川话',
}
SR = 24000
TRIM = ('silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,areverse,'
        'silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,areverse')


def read_script(path):
    """返回 [(text, pause_before_is_paragraph)]"""
    out, para = [], False
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        s = raw.strip()
        if not s:
            para = bool(out)
            continue
        if s.startswith('#'):
            continue
        out.append((s, para))
        para = False
    return out


def lint(lines):
    bad = 0
    for i, (t, _) in enumerate(lines, 1):
        if re.search(r'\d\s*-\s*\d', t):
            print(f'[WARN] 第 {i} 行含 数字-数字，会读成"减"：{t}', file=sys.stderr); bad += 1
        if re.search(r'[*`\[\]|]', t):
            print(f'[WARN] 第 {i} 行有 markdown 残留：{t}', file=sys.stderr); bad += 1
    return bad


def synth(text, key, model, voice, dst, retries=4):
    import dashscope
    for attempt in range(retries):
        try:
            r = dashscope.MultiModalConversation.call(model=model, api_key=key, text=text, voice=voice, stream=False)
            url = getattr(getattr(getattr(r, 'output', None), 'audio', None), 'url', None)
            if url:
                tmp = dst.with_suffix('.part')
                urllib.request.urlretrieve(url, tmp)  # 链接 24 小时有效，立即下载
                tmp.rename(dst)
                return
            code = getattr(r, 'code', '') or ''
            msg = f'{getattr(r, "status_code", "?")} {code} {getattr(r, "message", "")}'
        except Exception as e:  # 网络抖动
            code, msg = '', repr(e)
        wait = 30 if 'Throttling' in code else 3 * (attempt + 1)  # 429 歇 30 s 即恢复，非额度问题
        print(f'[RETRY] {dst.name}: {msg}，{wait}s 后重试', file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f'合成失败 {dst.name}：{msg}（连续空返回先查额度/欠费）')


def trimmed(src, dst):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-af', TRIM, '-ar', str(SR), '-ac', '1', str(dst)], check=True)
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                          '-of', 'csv=p=0', str(dst)]).strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('script', nargs='?')
    ap.add_argument('--out-dir')
    ap.add_argument('--voice', default='Cherry', choices=list(VOICES))
    ap.add_argument('--model', default='qwen-tts-latest', choices=MODELS)
    ap.add_argument('--key-file', help='只含 key 的文本文件；不给就读环境变量 DASHSCOPE_API_KEY')
    ap.add_argument('--gap', type=float, default=0.35, help='句间停顿秒数')
    ap.add_argument('--para-gap', type=float, default=0.9, help='空行处停顿秒数')
    ap.add_argument('--lead', type=float, default=0.3, help='整轨开头留白')
    ap.add_argument('--workers', type=int, default=2, help='并发（2 路稳定，3 路会撞 429）')
    ap.add_argument('--list-voices', action='store_true')
    a = ap.parse_args()
    if a.list_voices:
        for k, v in VOICES.items():
            print(f'{k:8s} {v}')
        return
    if not a.script or not a.out_dir:
        ap.error('需要 台本 与 --out-dir')

    lines = read_script(a.script)
    if not lines:
        sys.exit('台本为空')
    if lint(lines):
        print('[WARN] 上面的行建议先改台本再合成', file=sys.stderr)
    if a.key_file:
        key = Path(os.path.expanduser(a.key_file)).read_text().strip()
    else:
        key = os.environ.get('DASHSCOPE_API_KEY', '').strip()
    if not key:
        sys.exit('缺 key：设置环境变量 DASHSCOPE_API_KEY，或用 --key-file 指定')
    out = Path(a.out_dir); (out / 'lines').mkdir(parents=True, exist_ok=True)

    jobs = []
    for i, (t, _) in enumerate(lines, 1):
        h = hashlib.sha1(f'{a.model}|{a.voice}|{t}'.encode()).hexdigest()[:10]
        jobs.append((t, out / 'lines' / f'{i:03d}_{h}.wav'))
    todo = [(t, p) for t, p in jobs if not p.exists()]
    print(f'[INFO] {len(lines)} 句，{len(todo)} 句待合成（{sum(len(t) for t, _ in todo)} 字），'
          f'model={a.model} voice={a.voice}')
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(lambda tp: synth(tp[0], key, a.model, a.voice, tp[1]), todo))

    # 去首尾静音后按停顿拼接；时间表直接由片段长度累加得到，不需要对齐
    tdir = out / 'trimmed'; tdir.mkdir(exist_ok=True)
    concat, table, t = [], [], a.lead
    sil = lambda d: f"anullsrc=r={SR}:cl=mono:d={d:.3f}"
    parts = [('sil', a.lead)]
    for i, ((text, para), (_, src)) in enumerate(zip(lines, jobs), 1):
        if i > 1:
            g = a.para_gap if para else a.gap
            parts.append(('sil', g)); t += g
        dst = tdir / src.name
        d = trimmed(src, dst)
        table.append({'i': i, 'text': text, 'start': round(t, 3), 'end': round(t + d, 3)})
        parts.append(('wav', dst)); t += d
    parts.append(('sil', 0.5))

    args, flt = ['ffmpeg', '-v', 'error', '-y'], []
    for n, (kind, v) in enumerate(parts):
        args += ['-f', 'lavfi', '-i', sil(v)] if kind == 'sil' else ['-i', str(v)]
        flt.append(f'[{n}:a]')
    args += ['-filter_complex', ''.join(flt) + f'concat=n={len(parts)}:v=0:a=1[a]', '-map', '[a]',
             '-ar', str(SR), '-ac', '1', str(out / 'narration.wav')]
    subprocess.run(args, check=True)

    (out / 'narration.json').write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'script.txt').write_text('\n'.join(x['text'] for x in table) + '\n', encoding='utf-8')
    # align_lyrics.py --windows：行号 0 起，句子起止已知，逐字对齐只在本句区间里找
    (out / 'windows.json').write_text(json.dumps(
        {str(x['i'] - 1): [round(max(0, x['start'] - 0.15), 3), round(x['end'] + 0.15, 3)] for x in table}), encoding='utf-8')
    print(json.dumps({'wav': str(out / 'narration.wav'), 'json': str(out / 'narration.json'),
                      'lines': len(table), 'duration': round(t + 0.5, 3)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
