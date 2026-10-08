// 旁白插画模板的最小示例：两句示例旁白（src/data/narration-lyrics.json），每句一镜，动作卡在具体的字上。
// 做真片子时：tts.py / align_lyrics.py 产出的 lyrics.json 替换示例数据，照这个写法每句写一个 G(...) 镜头。
import React from 'react';
import {AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';
import {G, LINES} from './narration/kit';

export const NARR_DEMO_FRAMES = 30 * 9;

const useFonts = () => {
  const [h] = React.useState(() => delayRender('fonts'));
  React.useEffect(() => {
    const defs: [string, string][] = [['NotoSansSC-500.ttf', '500'], ['NotoSansSC-700.ttf', '700']];
    Promise.all(defs.map(async ([p, weight]) => {
      const f = new FontFace('NarrSans', `url(${staticFile(`narration/${p}`)})`, {weight}); await f.load(); document.fonts.add(f);
    })).then(() => continueRender(h)).catch(() => continueRender(h));
  }, [h]);
};

const SHOTS = [
  G(0, {bg: {color: '#F4EEE4'}, acts: [{who: 'kid', x: 960, expr: 'smile', wave: 'R', then: [{at: '旁白', expr: 'happy'}]}],
    items: [{k: 'bubble', who: 0, text: '你好！', at: '示例'}]}),
  G(1, {bg: {room: {wall: '#E9E1F2', floor: '#CDBFDD', window: true}}, acts: [{who: 'girl', x: 760, expr: 'calm', then: [{at: '替换', expr: 'happy'}]}, {who: 'boy', x: 1160, flip: true, expr: 'confused'}],
    items: [{k: 'q', who: 1, at: '台本'}, {k: 'spark', who: 0, at: '替换'}]}),
];

export const NarrationDemo: React.FC = () => {
  useFonts();
  const frame = useCurrentFrame();
  const t = frame / 30;
  let k = 0;
  for (let i = 0; i < SHOTS.length; i++) if (t >= LINES[SHOTS[i].li].start - 0.3) k = i;
  const line = LINES[SHOTS[k].li];
  return (
    <AbsoluteFill style={{background: '#F4EEE4'}}>
      <svg viewBox="0 0 1920 1080" width={1920} height={1080}>{SHOTS[k].fn(t, frame)}</svg>
      <div style={{position: 'absolute', bottom: 60, width: '100%', display: 'flex', justifyContent: 'center'}}>
        <div style={{background: 'rgba(42,40,51,0.72)', borderRadius: 16, padding: '10px 28px', fontFamily: 'NarrSans', fontSize: 34, fontWeight: 500, color: '#fff'}}>{line.text}</div>
      </div>
    </AbsoluteFill>
  );
};
