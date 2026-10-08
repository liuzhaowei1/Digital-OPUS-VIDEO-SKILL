// Project config (public/project.json): what the engine needs to know about this video that is not
// scene code. Everything is optional except duration; a video without a song runs on a synthetic
// constant beat grid (bpm, default 120) so beat-synced helpers keep working.
export interface ProjectJSON {
  title?: string;
  /** Seconds. With a song, data/audio.json's duration wins. */
  duration: number;
  /** Song file under public/ (e.g. "audio/song.mp3"); omit for a silent video. */
  audio?: string;
  /** Synthetic beat grid when there is no data/audio.json. */
  bpm?: number;
  /** Time of the first beat of the synthetic grid (s). */
  beatOffset?: number;
  /** Beats per bar of the synthetic grid. */
  beatsPerBar?: number;
  /** Load the CJK fonts (Noto Sans SC / Noto Serif SC, ~90 MB). Default true. */
  cjk?: boolean;
  /**
   * Optional HUD readout (a number that steps up over the video, like pdoom's P(doom)).
   * steps: [time, value] pairs; label: the caption above the digits; digits: decimals shown.
   */
  readout?: { label: string; steps: [number, number][]; digits?: number };
}

export let PROJECT: ProjectJSON = { duration: 10 };

export async function loadProject(): Promise<ProjectJSON> {
  const r = await fetch('project.json');
  if (!r.ok) throw new Error('public/project.json missing');
  PROJECT = await r.json();
  return PROJECT;
}
