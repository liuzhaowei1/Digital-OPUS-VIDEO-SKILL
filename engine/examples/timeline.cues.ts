// The edit, driven by cues.json — the SAME file synth_bgm.py builds the soundtrack from, so every cut
// lands on the transient the music puts there. Times in cues.json are beats of the constant grid.
import type { TimelineEntry } from './engine/engine';
import type { SceneClass } from './engine/scene';
import type { Lyrics } from './engine/lyrics';
import type { AudioData } from './engine/audio';
import cues from '../cues.json';   // project root; synth_bgm.py reads the same file

const modules = import.meta.glob<{ default: SceneClass }>('./scenes/*.ts');
const scene = (name: string) => () => {
  const m = modules[`./scenes/${name}.ts`];
  return m ? m() : Promise.reject(new Error(`scene module not found: scenes/${name}.ts`));
};

const WORDS = ['节奏', '间距', '字重', '对比', '流动', '意图', '时间', '留白', '密度', '张力', '停顿', '决定'];

export function makeTimeline(_ly: Lyrics, au: AudioData): TimelineEntry[] {
  const at = (b: number) => (cues.beatOffset ?? 0) + (b * 60) / cues.bpm;
  const marks = [0, ...cues.cuts, (au.duration - (cues.beatOffset ?? 0)) * cues.bpm / 60];
  const out: TimelineEntry[] = [];
  for (let i = 0; i + 1 < marks.length; i++) {
    const b = marks[i]!;
    const title = b === 0 ? '从一个问题开始' : b >= cues.tail ? '每一帧都是决定' : WORDS[i % WORDS.length]!;
    out.push({ id: `c${i}`, load: scene('demo'), start: at(b), end: at(marks[i + 1]!), params: { paper: i % 2 === 1, title } });
  }
  return out;
}
