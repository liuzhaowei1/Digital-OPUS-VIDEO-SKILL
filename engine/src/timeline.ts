// The edit: which scene plays when. With a song, anchor cuts to lyric lines and snap them to the beat grid
// (see examples/timeline.pdoom.ts: cut() = last beat before a line's first word, after() = nearest downbeat).
// Without a song, the synthetic grid from project.json (bpm) still gives beats to cut on.
import type { TimelineEntry } from './engine/engine';
import type { SceneClass } from './engine/scene';
import type { Lyrics } from './engine/lyrics';
import type { AudioData } from './engine/audio';

// Scene modules are discovered lazily so a missing/broken scene never breaks the build.
const modules = import.meta.glob<{ default: SceneClass }>('./scenes/*.ts');
const scene = (name: string) => () => {
  const m = modules[`./scenes/${name}.ts`];
  return m ? m() : Promise.reject(new Error(`scene module not found: scenes/${name}.ts`));
};

export function makeTimeline(_ly: Lyrics, au: AudioData): TimelineEntry[] {
  const beat = (i: number) => au.timeOfBeat(i);
  return [
    { id: 'demo-dark', load: scene('demo'), start: 0, end: beat(10) },
    { id: 'demo-paper', load: scene('demo'), start: beat(10), end: au.duration, params: { paper: true, title: '再到一个伙伴' } },
  ];
}
