import React from 'react';
import {Easing, interpolate} from 'remotion';
import lyrics from '../../data/narration-lyrics.json';
import env from '../../data/narration-env.json';
import {Anger, Bubble, Char, Cloud, Expr, Heart, INK, Question, Room, Sparkle, Sweat, Tears, Who} from './Chars';

type Word = {w: string; start: number; end: number};
export type Line = {i: number; text: string; start: number; end: number; words: Word[]};
export const LINES = (lyrics as {lines: Line[]}).lines;
const ENV = (env as {rms: number[]}).rms;

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const outBack = Easing.out(Easing.back(1.8));
export const outCubic = Easing.out(Easing.cubic);
const seqOf = (li: number) => LINES[li].words.map((w) => w.w[0]).join('');
export const wt = (li: number, word: string) => {
  const k = seqOf(li).indexOf(word);
  if (k < 0) throw new Error(`word not found: line ${li} "${word}"`);
  return LINES[li].words[k].start;
};
export const wend = (li: number, word: string) => {
  const k = seqOf(li).indexOf(word);
  if (k < 0) throw new Error(`word not found: line ${li} "${word}"`);
  return LINES[li].words[k + word.length - 1].end;
};
export const pop = (t: number, t0: number, d = 0.35) => interpolate(t, [t0, t0 + d], [0, 1], {...clamp, easing: outBack});
export const fade = (t: number, t0: number, d = 0.3) => interpolate(t, [t0, t0 + d], [0, 1], clamp);
export const vol = (frame: number) => ENV[Math.min(ENV.length - 1, frame)] ?? 0;
export type ShotFn = (t: number, frame: number) => React.ReactNode;

// ---------- 通用小部件 ----------
export const Tag: React.FC<{x?: number; y?: number; text: string; op?: number; c?: string; fs?: number}> = ({x = 960, y = 150, text, op = 1, c = '#D9674E', fs = 38}) => (
  <g opacity={op}>
    <rect x={x - text.length * fs * 0.58 - 26} y={y - fs} width={text.length * fs * 1.16 + 52} height={fs * 1.7} rx={fs * 0.85} fill={c} />
    <text x={x} y={y + fs * 0.18} fontSize={fs} fontWeight={700} fill="#fff" textAnchor="middle" fontFamily="NarrSans">{text}</text>
  </g>
);
export const Txt: React.FC<{x: number; y: number; text: string; fs?: number; c?: string; op?: number; w?: number}> = ({x, y, text, fs = 44, c = INK, op = 1, w = 700}) => (
  <text x={x} y={y} fontSize={fs} fontWeight={w} fill={c} textAnchor="middle" fontFamily="NarrSans" opacity={op}>{text}</text>
);
export const Card: React.FC<{x: number; y: number; w: number; h?: number; text: string; fs?: number; c?: string; fg?: string; s?: number; op?: number}> = ({x, y, w, h = 100, text, fs = 40, c = '#fff', fg = INK, s = 1, op = 1}) => (
  <g transform={`translate(${x},${y}) scale(${s})`} opacity={op}>
    <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={22} fill={c} stroke={INK} strokeWidth={5} />
    <text x={0} y={fs * 0.36} fontSize={fs} fontWeight={700} fill={fg} textAnchor="middle" fontFamily="NarrSans">{text}</text>
  </g>
);
export const Cross: React.FC<{x: number; y: number; s?: number}> = ({x, y, s = 1}) => (
  <g transform={`translate(${x},${y}) scale(${s})`} stroke="#E0453A" strokeWidth={14} strokeLinecap="round"><line x1={-40} y1={-40} x2={40} y2={40} /><line x1={40} y1={-40} x2={-40} y2={40} /></g>
);
export const Check: React.FC<{x: number; y: number; s?: number}> = ({x, y, s = 1}) => (
  <g transform={`translate(${x},${y}) scale(${s})`}><circle r={40} fill="#5FAE93" stroke={INK} strokeWidth={4} /><path d="M -18,0 L -4,14 L 20,-14" fill="none" stroke="#fff" strokeWidth={9} strokeLinecap="round" /></g>
);
// 砖墙：built 0..1 垒到几成，door 0..1 门开多大
export const Wall: React.FC<{x: number; y: number; w?: number; rows?: number; built?: number; door?: number; c?: string}> = ({x, y, w = 560, rows = 6, built = 1, door = 0, c = '#6F93D6'}) => {
  const bh = 44, bw = 88;
  const n = Math.round(rows * built);
  const els: React.ReactNode[] = [];
  for (let r = 0; r < n; r++) {
    const off = r % 2 ? bw / 2 : 0;
    for (let bx = -w / 2 - off; bx < w / 2; bx += bw) {
      const x0 = Math.max(bx, -w / 2), x1 = Math.min(bx + bw, w / 2);
      const mid = (x0 + x1) / 2;
      if (door > 0 && Math.abs(mid) < door * 130 && r < rows - 1) continue;
      els.push(<rect key={`${r}-${bx}`} x={x0 + 2} y={-(r + 1) * bh + 2} width={x1 - x0 - 4} height={bh - 4} rx={6} fill={c} stroke={INK} strokeWidth={4} />);
    }
  }
  return <g transform={`translate(${x},${y})`}>{els}</g>;
};
export const Snow: React.FC<{f: number; op?: number}> = ({f, op = 1}) => (
  <g opacity={op}>{Array.from({length: 26}, (_, k) => {
    const x = (k * 173) % 1920 + Math.sin(f / 20 + k) * 30, y = ((f * (2 + (k % 3)) + k * 97) % 1100) - 20;
    return <circle key={k} cx={x} cy={y} r={5 + (k % 3) * 2} fill="#fff" opacity={0.85} />;
  })}</g>
);
export const Meter: React.FC<{x: number; y: number; h?: number; label?: string; line?: number}> = ({x, y, h = 620, label, line}) => (
  <g transform={`translate(${x},${y})`}>
    <rect x={-36} y={-h} width={72} height={h} rx={36} fill="#fff" stroke={INK} strokeWidth={5} />
    {Array.from({length: 11}, (_, k) => <g key={k}><line x1={36} y1={-k * (h / 10)} x2={56} y2={-k * (h / 10)} stroke={INK} strokeWidth={4} /><text x={82} y={-k * (h / 10) + 10} fontSize={28} fill={INK} fontFamily="NarrSans" textAnchor="middle">{k}</text></g>)}
    {line !== undefined && <line x1={-70} y1={-line * h} x2={70} y2={-line * h} stroke="#E0453A" strokeWidth={8} strokeDasharray="14 8" />}
    {label && <text x={0} y={50} fontSize={34} fontWeight={700} fill={INK} textAnchor="middle" fontFamily="NarrSans">{label}</text>}
  </g>
);
export const Balance: React.FC<{x: number; y: number; tilt: number; l?: React.ReactNode; r?: React.ReactNode}> = ({x, y, tilt, l, r}) => (
  <g transform={`translate(${x},${y})`}>
    <path d="M -80,0 L 80,0 L 20,-40 L -20,-40 Z" fill="#C9A96A" stroke={INK} strokeWidth={5} />
    <rect x={-10} y={-360} width={20} height={320} fill="#C9A96A" stroke={INK} strokeWidth={5} />
    <g transform={`translate(0,-360) rotate(${tilt})`}>
      <rect x={-330} y={-10} width={660} height={20} rx={10} fill="#C9A96A" stroke={INK} strokeWidth={5} />
      {[-310, 310].map((px, k) => (
        <g key={k} transform={`translate(${px},0) rotate(${-tilt})`}>
          <line x1={-60} y1={140} x2={0} y2={0} stroke={INK} strokeWidth={3} /><line x1={60} y1={140} x2={0} y2={0} stroke={INK} strokeWidth={3} />
          <path d="M -90,140 L 90,140 Q 60,190 0,190 Q -60,190 -90,140 Z" fill="#E3C98F" stroke={INK} strokeWidth={5} />
          <g transform="translate(0,130)">{k === 0 ? l : r}</g>
        </g>
      ))}
    </g>
  </g>
);
export const Board: React.FC<{x: number; y: number; w?: number; h?: number; lines: string[]; shown?: number; title?: string; c?: string}> = ({x, y, w = 560, h = 380, lines, shown = lines.length, title, c = '#3F5C4E'}) => (
  <g transform={`translate(${x},${y})`}>
    <rect x={-w / 2 - 14} y={-h / 2 - 14} width={w + 28} height={h + 28} rx={16} fill="#B98A5E" stroke={INK} strokeWidth={5} />
    <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={8} fill={c} />
    {title && <text x={0} y={-h / 2 + 64} fontSize={46} fontWeight={700} fill="#fff" textAnchor="middle" fontFamily="NarrSans">{title}</text>}
    {lines.slice(0, shown).map((s, k) => <text key={k} x={-w / 2 + 50} y={-h / 2 + (title ? 140 : 80) + k * 66} fontSize={40} fill="#F4EEE4" fontFamily="NarrSans">{s}</text>)}
  </g>
);
export const Dial: React.FC<{x: number; y: number; v: number; label: string}> = ({x, y, v, label}) => {
  const a = -135 + v * 270;
  return (
    <g transform={`translate(${x},${y})`}>
      <circle r={150} fill="#fff" stroke={INK} strokeWidth={6} />
      {Array.from({length: 10}, (_, k) => { const b = (-135 + k * 30) * Math.PI / 180; return <line key={k} x1={Math.sin(b) * 118} y1={-Math.cos(b) * 118} x2={Math.sin(b) * 138} y2={-Math.cos(b) * 138} stroke={INK} strokeWidth={5} />; })}
      <text x={-90} y={110} fontSize={30} fill={INK} fontFamily="NarrSans" textAnchor="middle">低</text><text x={90} y={110} fontSize={30} fill={INK} fontFamily="NarrSans" textAnchor="middle">高</text>
      <g transform={`rotate(${a})`}><path d="M -12,0 L 0,-110 L 12,0 Z" fill="#E0453A" stroke={INK} strokeWidth={4} /></g>
      <circle r={20} fill={INK} />
      <text x={0} y={210} fontSize={40} fontWeight={700} fill={INK} textAnchor="middle" fontFamily="NarrSans">{label}</text>
    </g>
  );
};
export const Battery: React.FC<{x: number; y: number; v: number}> = ({x, y, v}) => (
  <g transform={`translate(${x},${y})`}>
    <rect x={-120} y={-60} width={240} height={120} rx={20} fill="#fff" stroke={INK} strokeWidth={6} />
    <rect x={120} y={-24} width={22} height={48} rx={6} fill={INK} />
    <rect x={-104} y={-44} width={208 * v} height={88} rx={10} fill={v < 0.25 ? '#E0453A' : '#5FAE93'} />
  </g>
);
export const Ball: React.FC<{x: number; y: number; r?: number; c?: string; label?: string}> = ({x, y, r = 60, c = '#F3A6B8', label}) => (
  <g transform={`translate(${x},${y})`}>
    <circle r={r} fill={c} stroke={INK} strokeWidth={5} /><ellipse cx={-r * 0.35} cy={-r * 0.35} rx={r * 0.22} ry={r * 0.14} fill="#fff" opacity={0.7} />
    {label && <text x={0} y={r * 0.2} fontSize={r * 0.5} fontWeight={700} fill={INK} textAnchor="middle" fontFamily="NarrSans">{label}</text>}
  </g>
);
export const Gear: React.FC<{x: number; y: number; r?: number; a?: number; c?: string}> = ({x, y, r = 70, a = 0, c = '#9AA6BA'}) => (
  <g transform={`translate(${x},${y}) rotate(${a})`}>
    {Array.from({length: 8}, (_, k) => <rect key={k} x={-14} y={-r - 22} width={28} height={36} rx={6} fill={c} stroke={INK} strokeWidth={4} transform={`rotate(${k * 45})`} />)}
    <circle r={r} fill={c} stroke={INK} strokeWidth={5} /><circle r={r * 0.35} fill="#fff" stroke={INK} strokeWidth={5} />
  </g>
);
export const Calendar: React.FC<{x: number; y: number; n: number}> = ({x, y, n}) => (
  <g transform={`translate(${x},${y})`}>
    <rect x={-110} y={-120} width={220} height={240} rx={18} fill="#fff" stroke={INK} strokeWidth={5} />
    <rect x={-110} y={-120} width={220} height={64} rx={18} fill="#E0453A" stroke={INK} strokeWidth={5} />
    <text x={0} y={60} fontSize={110} fontWeight={700} fill={INK} textAnchor="middle" fontFamily="NarrSans">{n}</text>
  </g>
);
export const Cap: React.FC<{x: number; y: number; s?: number}> = ({x, y, s = 1}) => (
  <g transform={`translate(${x},${y}) scale(${s})`}>
    <path d="M -150,0 L 0,-60 L 150,0 L 0,60 Z" fill={INK} /><rect x={-80} y={10} width={160} height={50} fill={INK} />
    <path d="M 120,10 L 130,90" stroke="#FFD166" strokeWidth={8} /><circle cx={130} cy={96} r={12} fill="#FFD166" />
  </g>
);
export const Parallel: React.FC<{t: number; t0: number}> = ({t, t0}) => {
  const p = interpolate(t, [t0, t0 + 1.5], [0, 1], {...clamp, easing: outCubic});
  return (
    <g>
      <path d={`M 360,480 C 700,${440 - 40 * p} 1200,${440 - 40 * p} ${360 + 1200 * p},${470 - 20 * p}`} fill="none" stroke="#6F93D6" strokeWidth={14} strokeLinecap="round" />
      <path d={`M 360,600 C 700,${640 + 40 * p} 1200,${640 + 40 * p} ${360 + 1200 * p},${610 + 20 * p}`} fill="none" stroke="#F3A6B8" strokeWidth={14} strokeLinecap="round" />
    </g>
  );
};

// ---------- 通用镜头模板 ----------
export type Act = {
  who: Who; x: number; y?: number; s?: number; expr?: Expr; flip?: boolean; aL?: number; aR?: number; mask?: boolean; lean?: number; op?: number; tears?: boolean;
  then?: {at: string; expr?: Expr; aL?: number; aR?: number; mask?: boolean; tears?: boolean; flip?: boolean}[];
  talk?: [string, string];            // 从哪个词说到哪个词（嘴按音量动）
  walk?: {at: string; to: number; dur?: number; stiff?: boolean};
  wave?: 'L' | 'R';                   // 某只手持续摆动
};
export type It = {
  k: 'bubble' | 'think' | 'tag' | 'anger' | 'q' | 'sweat' | 'heart' | 'spark' | 'cloud' | 'text' | 'card' | 'cross' | 'check';
  at?: string; dt?: number; until?: string;
  who?: number; x?: number; y?: number; text?: string; w?: number; s?: number; c?: string; storm?: boolean; fs?: number; outline?: boolean;
};
export type Bg = {room?: {wall: string; floor: string; window?: boolean; sofa?: boolean}; color?: string; sepia?: boolean; vignette?: boolean};

const BgEl: React.FC<{bg: Bg}> = ({bg}) => (
  <>
    {bg.room ? <Room {...bg.room} /> : <rect width={1920} height={1080} fill={bg.color ?? '#F4EEE4'} />}
    {bg.sepia && <rect width={1920} height={1080} fill="#E6D3B3" opacity={bg.room ? 0.55 : 0} />}
  </>
);

export const G = (li: number, cfg: {bg: Bg; acts?: Act[]; items?: It[]; under?: ShotFn; over?: ShotFn}): {li: number; fn: ShotFn} => ({
  li,
  fn: (t, f) => {
    const T = (at?: string, dt?: number) => (at ? wt(li, at) : LINES[li].start + (dt ?? 0.2));
    const acts = (cfg.acts ?? []).map((a, idx) => {
      let st = {...a};
      for (const th of a.then ?? []) if (t >= wt(li, th.at)) st = {...st, ...th};
      const s = a.s ?? 1.1;
      let x = a.x, bob = 0;
      if (a.walk) {
        const w0 = wt(li, a.walk.at), d = a.walk.dur ?? 1.2;
        const p = interpolate(t, [w0, w0 + d], [0, 1], clamp);
        const pp = a.walk.stiff ? Math.floor(p * 6) / 6 : p;
        x = a.x + (a.walk.to - a.x) * pp;
        if (p > 0 && p < 1) bob = -Math.abs(Math.sin(t * (a.walk.stiff ? 11 : 14))) * 12;
      }
      const talk = a.talk && t >= wt(li, a.talk[0]) && t <= wend(li, a.talk[1]) + 0.08 ? vol(f) : 0;
      const wav = (k: 'L' | 'R') => (a.wave === k ? 70 + Math.sin(f / 2.5) * 22 : undefined);
      return {...st, x, y: a.y ?? 900, s, bob, talk, idx, aL: wav('L') ?? st.aL, aR: wav('R') ?? st.aR};
    });
    const head = (i: number) => {const a = acts[i]; return {x: a.x, top: a.y - 390 * a.s, dir: a.flip ? -1 : 1};};
    return (
      <g>
        <BgEl bg={cfg.bg} />
        {cfg.under?.(t, f)}
        {acts.map((a) => (
          <g key={a.idx}>
            <Char who={a.who} x={a.x} y={a.y} s={a.s} frame={f} expr={a.expr} flip={a.flip} aL={a.aL} aR={a.aR} mask={a.mask} lean={a.lean} bob={a.bob} talk={a.talk} blinkSeed={a.idx * 3 + li} opacity={a.op} />
            {a.tears && <g transform={`translate(${a.x},${a.y}) scale(${a.s}) translate(${-a.x},${-a.y})`}><Tears x={a.x} y={a.y} frame={f} /></g>}
          </g>
        ))}
        {cfg.over?.(t, f)}
        {(cfg.items ?? []).map((it, k) => {
          const t0 = T(it.at, it.dt);
          if (t < t0) return null;
          if (it.until && t > wt(li, it.until)) return null;
          const p = pop(t, t0), o = fade(t, t0, 0.2);
          const h = it.who !== undefined ? head(it.who) : null;
          switch (it.k) {
            case 'bubble': case 'think': {
              const w = it.w ?? Math.max(220, (it.text ?? '').length * 46 + 80);
              const bx = it.x ?? (h ? h.x + h.dir * (w / 2 + 40) : 960), by = it.y ?? (h ? h.top - 80 : 300);
              return <Bubble key={k} x={bx} y={by} w={w} text={it.text ?? ''} fs={it.fs ?? 44} tail={h && h.dir < 0 ? 'r' : 'l'} think={it.k === 'think'} op={o} sc={p} />;
            }
            case 'tag': return <Tag key={k} x={it.x} y={it.y} text={it.text ?? ''} op={o} c={it.c} />;
            case 'anger': return <Anger key={k} x={it.x ?? (h ? h.x + 110 : 0)} y={it.y ?? (h ? h.top + 50 : 0)} s={p * (1 + 0.1 * Math.sin(f / 3))} />;
            case 'q': return <Question key={k} x={it.x ?? (h ? h.x + 105 : 0)} y={it.y ?? (h ? h.top + 20 : 0)} s={p * (it.s ?? 1)} c={it.c} />;
            case 'sweat': return <Sweat key={k} x={it.x ?? (h ? h.x - 105 : 0)} y={it.y ?? (h ? h.top + 110 : 0)} s={p} />;
            case 'heart': return <Heart key={k} x={it.x ?? (h ? h.x : 0)} y={it.y ?? (h ? h.top - 70 : 0)} s={p * (it.s ?? 1)} c={it.c} outline={it.outline} />;
            case 'spark': return <g key={k}>{[0, 1, 2].map((j) => <Sparkle key={j} x={(it.x ?? (h ? h.x : 960)) - 120 + j * 120} y={(it.y ?? (h ? h.top - 20 : 300)) - (j % 2) * 50} s={0.55 * pop(t, t0 + j * 0.1) * (1 + 0.15 * Math.sin(f / 5 + j))} c={it.c} />)}</g>;
            case 'cloud': return <Cloud key={k} x={it.x ?? (h ? h.x : 960)} y={it.y ?? (h ? h.top - 110 : 300)} s={p * (it.s ?? 1)} storm={it.storm} frame={f} />;
            case 'text': return <Txt key={k} x={it.x ?? 960} y={it.y ?? 200} text={it.text ?? ''} fs={it.fs ?? 56} c={it.c} op={o} />;
            case 'card': return <Card key={k} x={it.x ?? 960} y={it.y ?? 300} w={it.w ?? 420} text={it.text ?? ''} fs={it.fs ?? 40} c={it.c ?? '#fff'} s={p} />;
            case 'cross': return <Cross key={k} x={it.x ?? 960} y={it.y ?? 300} s={p * (it.s ?? 1)} />;
            case 'check': return <Check key={k} x={it.x ?? 960} y={it.y ?? 300} s={p * (it.s ?? 1)} />;
          }
          return null;
        })}
        {cfg.bg.vignette && <rect width={1920} height={1080} fill="url(#vig)" />}
        {cfg.bg.sepia && <Frame />}
      </g>
    );
  },
});

// 章节卡
export const CH = (li: number, n: string, title: string, c: string, who: Who = 'boy', expr: Expr = 'calm'): {li: number; fn: ShotFn} => ({
  li,
  fn: (t, f) => {
    const t0 = LINES[li].start;
    return (
      <g>
        <rect width={1920} height={1080} fill={c} />
        <circle cx={1500} cy={560} r={300 * pop(t, t0, 0.5)} fill="#fff" opacity={0.35} />
        <Char who={who} x={1500} y={860} s={1.1} frame={f} expr={expr} />
        <g transform={`translate(${interpolate(t, [t0 - 0.2, t0 + 0.4], [-80, 0], {...clamp, easing: outCubic})},0)`} opacity={fade(t, t0 - 0.2, 0.4)}>
          <text x={200} y={480} fontSize={150} fontWeight={700} fill="#fff" fontFamily="NarrSans">{n}</text>
          <rect x={206} y={530} width={120} height={8} fill="#fff" />
          <text x={200} y={650} fontSize={66} fontWeight={700} fill={INK} fontFamily="NarrSans">{title}</text>
        </g>
      </g>
    );
  },
});
export {INK, Heart, Cloud, Bubble, Question, Sparkle, Anger, Sweat, Char};
