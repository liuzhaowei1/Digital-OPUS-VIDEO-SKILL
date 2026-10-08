// Template scene: one of each building block — a fullscreen shader (engraved hatching + heat glow),
// a GPU line batch (a spark drawing an arc), and a Canvas2D type layer (CJK 黑体/宋体 + mono), all
// driven by time and the beat grid. Copy it as the starting point of a new scene, then delete it.
import { Scene, type Frame } from '../engine/scene';
import { FSPass, Layer2D, W, H } from '../engine/gl';
import { LineBatch } from '../engine/lines';
import { LIN, rgba } from '../engine/palette';
import { F, font } from '../engine/type';
import { clamp, ease, prog, TAU } from '../engine/util';

export default class Demo extends Scene {
  bg = new FSPass(/* glsl */ `
    uniform float t, pulse, paper;
    void main() {
      vec2 p = (FRAG_PX - vec2(${W / 2}.0, ${H / 2}.0)) / ${H / 2}.0;   // -1..1 vertically, logical px based
      float r = length(p - vec2(0.45, 0.0));
      // a lit sphere: darkness from a fixed light, drawn as engraving lines
      float z = sqrt(max(0.0, 1.0 - (r / 0.55) * (r / 0.55)));
      vec3 n = normalize(vec3((p - vec2(0.45, 0.0)) / 0.55, z));
      float lit = sat(dot(n, normalize(vec3(-0.5, 0.6, 0.6))));
      float ink = r < 0.55 ? engrave(FRAG_PX, 1.0 - lit, 0.11, 0.6 + 0.1 * sin(t * 0.5)) : 0.0;
      vec3 base = mix(C_INK, C_BONE, paper);
      vec3 line = mix(C_BONE * 0.8, C_INK, paper);
      vec3 col = mix(base, line, ink);
      col += heat(0.55 + 0.4 * pulse) * pulse * smoothstep(0.62, 0.5, r) * 0.35;  // beat glow
      fragColor = vec4(col, 1.0);
    }`, { t: { value: 0 }, pulse: { value: 0 }, paper: { value: 0 } });
  lines = new LineBatch(4096);
  text = new Layer2D();

  render(f: Frame, out: any) {
    const { renderer, comp } = this.ctx;
    const paper = this.ctx.params.paper ? 1 : 0;
    const pulse = Math.pow(1 - f.beatPhase, 3);                       // 1 on each beat, decays
    this.bg.u.t!.value = f.t; this.bg.u.pulse!.value = pulse; this.bg.u.paper!.value = paper;
    this.bg.render(renderer, out);

    // the spark: draws an arc over the scene's first 70%, head glows (linear values > 1 bloom)
    const L = this.lines; L.clear();
    const cx = W / 2 + 0.45 * H / 2, cy = H / 2, R = 0.62 * H / 2;
    const k = prog(f.p, 0, 0.7, ease.inOutCubic), N = 240;
    let hx = cx + R, hy = cy;
    for (let i = 0; i < N * k; i++) {
      const a0 = (i / N) * TAU, a1 = ((i + 1) / N) * TAU;
      L.seg2(cx + R * Math.cos(a0), cy + R * Math.sin(a0), cx + R * Math.cos(a1), cy + R * Math.sin(a1), 1.6, LIN.signal, 0.9);
      hx = cx + R * Math.cos(a1); hy = cy + R * Math.sin(a1);
    }
    for (let j = 0; j < 12; j++) {                                   // a few radial sparks at the head
      const a = j * 0.52 + f.t * 3, l = 6 + 10 * pulse;
      L.seg2(hx, hy, hx + l * Math.cos(a), hy + l * Math.sin(a), 1.2, [LIN.ember[0] * 3, LIN.ember[1] * 3, LIN.ember[2] * 3], 0.8);
    }
    L.render(renderer, out);

    // type: CJK title revealed one character per beat, a serif line, a mono annotation
    const c = this.text.ctx; this.text.clear();
    const title = this.ctx.params.title ?? '从一个问题开始';
    const shown = clamp(Math.floor(f.beat - this.ctx.audio.beatAt(this.ctx.start)) + 1, 0, title.length);
    c.font = font(F.hei(900), 120);
    c.fillStyle = paper ? rgba('ink') : rgba('bone');
    let x = 140;
    for (let i = 0; i < title.length; i++) {
      c.fillStyle = i < shown ? (i === shown - 1 ? rgba('signal') : paper ? rgba('ink') : rgba('bone')) : rgba(paper ? 'ink' : 'bone', 0.12);
      c.fillText(title[i]!, x, 480);
      x += c.measureText(title[i]!).width;
    }
    c.font = font(F.song(400), 40);
    c.fillStyle = rgba(paper ? 'ink' : 'bone', 0.75);
    c.fillText('宋体用于引文与神圣时刻 · 黑体是主声音', 144, 560);
    c.font = font(F.mono(400), 16);
    c.fillStyle = rgba('signal', 0.9);
    c.fillText(`t = ${f.t.toFixed(2)} s   beat ${f.beat.toFixed(2)}   p ${f.p.toFixed(2)}`, 144, 620);
    comp.draw(renderer, this.text.upload(), out);
    return { bloom: 0.7, paper };
  }
}
