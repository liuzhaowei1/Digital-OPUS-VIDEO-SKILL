import React from 'react';

// Q 版角色（纯 SVG）。坐标原点在两脚之间的地面，头心约在 (0,-270)。
export const INK = '#3A3140';
const SW = 5;

export type Expr = 'smile' | 'calm' | 'happy' | 'confused' | 'angry' | 'sad' | 'cry' | 'flat' | 'shock';
export type Who = 'boy' | 'girl' | 'kid';

const PALETTE: Record<Who, {skin: string; hair: string; top: string; bottom: string}> = {
  boy: {skin: '#FFE1CC', hair: '#3A3140', top: '#6F93D6', bottom: '#44506E'},
  girl: {skin: '#FFE4D2', hair: '#8A5140', top: '#F3A6B8', bottom: '#7C6FA8'},
  kid: {skin: '#FFE1CC', hair: '#3A3140', top: '#F4C95A', bottom: '#5B7FBF'},
};

export type CharProps = {
  who: Who;
  x: number; y: number; s?: number;
  expr?: Expr;
  aL?: number; aR?: number;       // 手臂外展角度，0 = 自然下垂，160 = 举过头顶，负值 = 向内（抱臂）
  flip?: boolean;                  // 面朝左
  frame: number;
  talk?: number;                   // 0..1 说话音量，>0 时嘴按音量张
  blinkSeed?: number;
  lean?: number;                   // 身体倾斜角度
  bob?: number;                    // 额外上下位移
  mask?: boolean;                  // 戴笑脸面具
  opacity?: number;
};

const Arm: React.FC<{x: number; a: number; c: string; skin: string}> = ({x, a, c, skin}) => (
  <g transform={`translate(${x},-148) rotate(${a})`}>
    <rect x={-16} y={-6} width={32} height={88} rx={16} fill={c} stroke={INK} strokeWidth={SW} />
    <circle cx={0} cy={88} r={18} fill={skin} stroke={INK} strokeWidth={SW} />
  </g>
);

const Eyes: React.FC<{expr: Expr; blink: boolean}> = ({expr, blink}) => {
  const arc = (d: string) => <path d={d} fill="none" stroke={INK} strokeWidth={6} strokeLinecap="round" />;
  if (expr === 'happy') return <>{arc('M -56,-256 Q -42,-274 -28,-256')}{arc('M 28,-256 Q 42,-274 56,-256')}</>;
  if (expr === 'cry') return <>{arc('M -56,-262 Q -42,-248 -28,-262')}{arc('M 28,-262 Q 42,-248 56,-262')}</>;
  if (expr === 'calm' || blink) return <>{arc('M -54,-256 L -30,-256')}{arc('M 30,-256 L 54,-256')}</>;
  const ry = expr === 'shock' ? 9 : 16, rx = expr === 'shock' ? 9 : 12;
  return (
    <>
      {[-42, 42].map((ex) => (
        <g key={ex}>
          <ellipse cx={ex} cy={-256} rx={rx} ry={ry} fill={INK} />
          <circle cx={ex + 4} cy={-262} r={4} fill="#fff" />
        </g>
      ))}
    </>
  );
};

const Brows: React.FC<{expr: Expr}> = ({expr}) => {
  const l = (d: string) => <path d={d} fill="none" stroke={INK} strokeWidth={6} strokeLinecap="round" />;
  if (expr === 'angry') return <>{l('M -62,-296 L -26,-284')}{l('M 62,-296 L 26,-284')}</>;
  if (expr === 'sad' || expr === 'cry') return <>{l('M -62,-284 L -28,-296')}{l('M 62,-284 L 28,-296')}</>;
  if (expr === 'confused') return <>{l('M -60,-292 L -28,-292')}{l('M 28,-302 Q 44,-310 60,-298')}</>;
  if (expr === 'shock') return <>{l('M -60,-300 Q -44,-308 -28,-300')}{l('M 28,-300 Q 44,-308 60,-300')}</>;
  return null;
};

const Mouth: React.FC<{expr: Expr; talk: number}> = ({expr, talk}) => {
  const st = {fill: 'none', stroke: INK, strokeWidth: 5, strokeLinecap: 'round' as const};
  if (talk > 0.02) return <ellipse cx={0} cy={-208} rx={10 + talk * 4} ry={3 + talk * 13} fill="#B5474F" stroke={INK} strokeWidth={4} />;
  switch (expr) {
    case 'smile': case 'happy': return <path d="M -18,-214 Q 0,-196 18,-214" {...st} />;
    case 'calm': return <path d="M -12,-212 Q 0,-204 12,-212" {...st} />;
    case 'flat': case 'confused': return <path d="M -13,-208 L 13,-208" {...st} />;
    case 'shock': return <ellipse cx={0} cy={-206} rx={9} ry={11} fill="#B5474F" stroke={INK} strokeWidth={4} />;
    case 'angry': return <path d="M -14,-202 Q 0,-214 14,-202" {...st} />;
    default: return <path d="M -16,-202 Q 0,-216 16,-202" {...st} />;
  }
};

const Hair: React.FC<{who: Who; c: string; front: boolean}> = ({who, c, front}) => {
  if (who === 'girl') {
    if (!front) return <path d="M -138,-262 C -150,-430 150,-430 138,-262 L 144,-168 C 96,-146 -96,-146 -144,-168 Z" fill={c} stroke={INK} strokeWidth={SW} />;
    return (
      <>
        <path d="M -122,-258 C -130,-405 130,-405 122,-258 C 104,-316 56,-322 36,-296 C 18,-326 -30,-332 -52,-304 C -76,-326 -112,-310 -122,-258 Z" fill={c} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
        <path d="M 78,-356 l 10,-22 l 10,22 l 22,4 l -16,14 l 4,22 l -20,-11 l -20,11 l 4,-22 l -16,-14 Z" fill="#FFD166" stroke={INK} strokeWidth={4} />
      </>
    );
  }
  if (!front) return null;
  return (
    <>
      <path d="M -120,-262 C -128,-408 128,-408 120,-262 C 110,-318 62,-326 34,-298 C 14,-330 -36,-336 -58,-304 C -80,-326 -112,-312 -120,-262 Z" fill={c} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
      <path d="M 6,-384 C 14,-420 50,-414 40,-392" fill="none" stroke={INK} strokeWidth={SW} strokeLinecap="round" />
    </>
  );
};

export const Char: React.FC<CharProps> = (p) => {
  const {who, frame, expr = 'smile', aL = 8, aR = 8, s = 1, talk = 0, blinkSeed = 0, lean = 0, bob = 0} = p;
  const P = PALETTE[who];
  const breath = Math.sin((frame + blinkSeed * 7) / 14) * 0.012;
  const cyc = (frame + blinkSeed * 37) % 100;
  const blink = cyc < 4 && expr !== 'happy' && expr !== 'cry';
  const skirt = who === 'girl';
  return (
    <g transform={`translate(${p.x},${p.y + bob}) scale(${(p.flip ? -1 : 1) * s},${s})`} opacity={p.opacity ?? 1}>
      <ellipse cx={0} cy={4} rx={80} ry={14} fill={INK} opacity={0.12} />
      <g transform={`rotate(${lean}) scale(1,${1 + breath})`} style={{transformOrigin: '0px 0px'}}>
        {/* legs */}
        {[-28, 28].map((lx) => (
          <g key={lx}>
            <rect x={lx - 16} y={-58} width={32} height={56} rx={12} fill={skirt ? P.skin : P.bottom} stroke={INK} strokeWidth={SW} />
            <ellipse cx={lx + 4} cy={-4} rx={24} ry={12} fill={INK} />
          </g>
        ))}
        {/* body */}
        <Arm x={-64} a={aL} c={P.top} skin={P.skin} />
        <Arm x={64} a={-aR} c={P.top} skin={P.skin} />
        <path d="M -70,-168 C -76,-120 -80,-80 -82,-48 L 82,-48 C 80,-80 76,-120 70,-168 C 40,-182 -40,-182 -70,-168 Z"
          fill={P.top} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
        {skirt
          ? <path d="M -84,-70 L 84,-70 L 100,-36 L -100,-36 Z" fill={P.bottom} stroke={INK} strokeWidth={SW} strokeLinejoin="round" />
          : <path d="M -30,-168 Q 0,-140 30,-168" fill="none" stroke={INK} strokeWidth={4} />}
        {/* head */}
        <Hair who={who} c={P.hair} front={false} />
        <circle cx={0} cy={-266} r={116} fill={P.skin} stroke={INK} strokeWidth={SW} />
        <ellipse cx={-74} cy={-218} rx={18} ry={11} fill="#F59AA0" opacity={expr === 'angry' ? 0.9 : 0.55} />
        <ellipse cx={74} cy={-218} rx={18} ry={11} fill="#F59AA0" opacity={expr === 'angry' ? 0.9 : 0.55} />
        {p.mask ? (
          <g>
            <ellipse cx={0} cy={-240} rx={92} ry={74} fill="#FFFDF6" stroke={INK} strokeWidth={SW} />
            <path d="M -56,-256 Q -42,-274 -28,-256 M 28,-256 Q 42,-274 56,-256" fill="none" stroke={INK} strokeWidth={6} strokeLinecap="round" />
            <path d="M -34,-218 Q 0,-180 34,-218" fill="none" stroke="#D9674E" strokeWidth={7} strokeLinecap="round" />
            <path d="M -92,-250 L -126,-262 M 92,-250 L 126,-262" stroke={INK} strokeWidth={4} />
          </g>
        ) : (
          <>
            <Brows expr={expr} />
            <Eyes expr={expr} blink={blink} />
            <Mouth expr={expr} talk={talk} />
          </>
        )}
        <Hair who={who} c={P.hair} front />
      </g>
    </g>
  );
};

// ---------- 情绪符号与道具 ----------
export const Anger: React.FC<{x: number; y: number; s?: number}> = ({x, y, s = 1}) => (
  <g transform={`translate(${x},${y}) scale(${s})`} stroke="#E0453A" strokeWidth={9} strokeLinecap="round" fill="none">
    <path d="M -30,-8 Q -10,-10 -8,-30" /><path d="M 30,-8 Q 10,-10 8,-30" />
    <path d="M -30,8 Q -10,10 -8,30" /><path d="M 30,8 Q 10,10 8,30" />
  </g>
);
export const Question: React.FC<{x: number; y: number; s?: number; c?: string}> = ({x, y, s = 1, c = INK}) => (
  <text x={x} y={y} fontSize={110 * s} fontWeight={900} fill={c} textAnchor="middle" fontFamily="NarrSans">?</text>
);
export const Sweat: React.FC<{x: number; y: number; s?: number}> = ({x, y, s = 1}) => (
  <path transform={`translate(${x},${y}) scale(${s})`} d="M 0,-30 C 16,-6 20,6 20,14 A 20,20 0 0 1 -20,14 C -20,6 -16,-6 0,-30 Z" fill="#8FC7F0" stroke={INK} strokeWidth={4} />
);
export const Sparkle: React.FC<{x: number; y: number; s?: number; c?: string}> = ({x, y, s = 1, c = '#FFD166'}) => (
  <path transform={`translate(${x},${y}) scale(${s})`} d="M 0,-36 Q 6,-6 36,0 Q 6,6 0,36 Q -6,6 -36,0 Q -6,-6 0,-36 Z" fill={c} stroke={INK} strokeWidth={3} />
);
export const Heart: React.FC<{x: number; y: number; s?: number; c?: string; outline?: boolean}> = ({x, y, s = 1, c = '#E8707A', outline}) => (
  <path transform={`translate(${x},${y}) scale(${s})`} d="M 0,30 C -50,-6 -48,-50 -18,-50 C -6,-50 0,-40 0,-33 C 0,-40 6,-50 18,-50 C 48,-50 50,-6 0,30 Z"
    fill={outline ? 'none' : c} stroke={outline ? c : INK} strokeWidth={outline ? 8 : 4} strokeDasharray={outline ? '14 10' : undefined} />
);
export const Tears: React.FC<{x: number; y: number; frame: number}> = ({x, y, frame}) => (
  <g>
    {[-42, 42].map((ex) => (
      <g key={ex}>
        {[0, 1, 2].map((k) => {
          const ph = ((frame * 2 + k * 18) % 54) / 54;
          return <ellipse key={k} cx={x + ex + (ex < 0 ? -6 : 6)} cy={y - 250 + ph * 90} rx={7} ry={11} fill="#8FC7F0" opacity={1 - ph} />;
        })}
      </g>
    ))}
  </g>
);

export const Bubble: React.FC<{x: number; y: number; w: number; h?: number; text: string; fs?: number; tail?: 'l' | 'r'; think?: boolean; op?: number; sc?: number}> =
  ({x, y, w, h = 110, text, fs = 44, tail = 'l', think, op = 1, sc = 1}) => (
    <g transform={`translate(${x},${y}) scale(${sc})`} opacity={op}>
      {think ? (
        <>
          <circle cx={tail === 'l' ? -w / 2 + 20 : w / 2 - 20} cy={h / 2 + 34} r={14} fill="#fff" stroke={INK} strokeWidth={4} />
          <circle cx={tail === 'l' ? -w / 2 + 2 : w / 2 - 2} cy={h / 2 + 62} r={8} fill="#fff" stroke={INK} strokeWidth={4} />
        </>
      ) : (
        <path d={tail === 'l' ? `M ${-w / 2 + 40},${h / 2 - 6} L ${-w / 2 + 10},${h / 2 + 44} L ${-w / 2 + 90},${h / 2 - 6}` : `M ${w / 2 - 40},${h / 2 - 6} L ${w / 2 - 10},${h / 2 + 44} L ${w / 2 - 90},${h / 2 - 6}`}
          fill="#fff" stroke={INK} strokeWidth={5} strokeLinejoin="round" />
      )}
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={think ? h / 2 : 30} fill="#fff" stroke={INK} strokeWidth={5} />
      {!think && <rect x={-w / 2 + 44} y={h / 2 - 9} width={40} height={8} fill="#fff" />}
      <text x={0} y={fs * 0.36} fontSize={fs} fontWeight={700} fill={INK} textAnchor="middle" fontFamily="NarrSans">{text}</text>
    </g>
  );

export const Cloud: React.FC<{x: number; y: number; s?: number; c?: string; storm?: boolean; frame?: number}> = ({x, y, s = 1, c = '#9AA6BA', storm, frame = 0}) => (
  <g transform={`translate(${x},${y}) scale(${s})`}>
    <path d="M -90,30 C -130,30 -130,-24 -88,-26 C -84,-70 -24,-80 -6,-44 C 14,-84 86,-70 80,-20 C 124,-18 124,30 86,30 Z" fill={c} stroke={INK} strokeWidth={5} />
    {storm && <path d="M -6,34 L -26,84 L 0,80 L -16,126 L 30,62 L 4,66 L 20,34 Z" fill="#FFD166" stroke={INK} strokeWidth={4} opacity={Math.floor(frame / 6) % 3 === 0 ? 0.3 : 1} />}
    {storm && [-60, 50].map((dx, k) => <line key={k} x1={dx} y1={44 + ((frame * 3 + k * 20) % 40)} x2={dx - 6} y2={60 + ((frame * 3 + k * 20) % 40)} stroke="#6FA8DC" strokeWidth={6} strokeLinecap="round" />)}
  </g>
);

export const Room: React.FC<{wall: string; floor: string; window?: boolean; sofa?: boolean}> = ({wall, floor, window = true, sofa}) => (
  <g>
    <rect x={0} y={0} width={1920} height={1080} fill={wall} />
    <rect x={0} y={840} width={1920} height={240} fill={floor} />
    <line x1={0} y1={840} x2={1920} y2={840} stroke={INK} strokeWidth={5} opacity={0.5} />
    {window && (
      <g transform="translate(1420,170)" opacity={0.9}>
        <rect width={300} height={340} rx={12} fill="#DCEBF5" stroke={INK} strokeWidth={5} />
        <line x1={150} y1={0} x2={150} y2={340} stroke={INK} strokeWidth={5} /><line x1={0} y1={170} x2={300} y2={170} stroke={INK} strokeWidth={5} />
        <path d="M -30,-10 C 20,120 -10,260 -40,360 L -40,-10 Z M 330,-10 C 280,120 310,260 340,360 L 340,-10 Z" fill="#F2C7B8" stroke={INK} strokeWidth={4} />
      </g>
    )}
    {sofa && (
      <g transform="translate(960,840)">
        <rect x={-330} y={-190} width={660} height={120} rx={40} fill="#C9B79C" stroke={INK} strokeWidth={5} />
        <rect x={-360} y={-100} width={720} height={90} rx={30} fill="#D8C7AC" stroke={INK} strokeWidth={5} />
        <rect x={-320} y={-10} width={24} height={10} fill={INK} /><rect x={296} y={-10} width={24} height={10} fill={INK} />
      </g>
    )}
    <g transform="translate(260,840)">
      <rect x={-40} y={-90} width={80} height={90} rx={10} fill="#E3A87E" stroke={INK} strokeWidth={5} />
      <path d="M 0,-90 C -60,-150 -70,-230 -10,-250 C 0,-200 0,-150 0,-90 M 0,-90 C 50,-160 80,-220 30,-270 C 10,-200 6,-150 0,-90" fill="#8CC08F" stroke={INK} strokeWidth={5} />
    </g>
  </g>
);
