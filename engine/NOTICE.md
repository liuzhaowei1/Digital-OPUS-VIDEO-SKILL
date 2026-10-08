# NOTICE

The engine in this template (src/engine/, index.html, scripts/render.mjs, examples/) is derived from
**mexicat/pdoom-video** — "I'm Upping My P(doom)" music video — by Giacomo Magnanini, MIT License
(see LICENSE), taken at commit bdbad53 (2026-09-28). The original README credits Claude (Opus 5.5) in
Claude Code for the concept, analysis, renderer and scenes.

Changes in this template: Node port of the Bun render script (ws), WSL/RTX GPU flags; project.json
(song and lyrics optional, synthetic beat grid); the P(doom) HUD generalised to a configurable Readout;
CJK fonts (Noto Sans SC / Noto Serif SC) with F.hei()/F.song(); CJK-safe lyric normalisation; fonts
served from a shared assets dir. examples/scenes/ are the original scenes, unmodified, for reference.

The song, lyrics and audio of the original video are NOT included (they belong to their authors).
Fonts are under their own licenses (SIL OFL / public domain), see docs/SETUP.md in the skill.
