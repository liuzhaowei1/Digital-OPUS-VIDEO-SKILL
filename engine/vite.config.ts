import { defineConfig, normalizePath, type Plugin } from 'vite';
import { cpSync, existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Fonts live outside the project (shared, ~130 MB, not in git): OPUS_ASSETS, else $OPUS_HOME/_assets (OPUS_HOME defaults to ~/opus-video).
// They are served at /fonts/… like the original repo's public/fonts, and copied into builds.
const ASSETS = process.env.OPUS_ASSETS ?? path.join(process.env.OPUS_HOME ?? path.join(os.homedir(), 'opus-video'), '_assets');
const FONTS = path.join(ASSETS, 'fonts');

function sharedFonts(): Plugin {
  return {
    name: 'shared-fonts',
    configureServer(server) {
      if (!existsSync(FONTS)) server.config.logger.warn(`fonts dir missing: ${FONTS}`);
      server.middlewares.use((req, _res, next) => {
        if (req.url?.startsWith('/fonts/')) req.url = `/@fs/${encodeURI(normalizePath(FONTS))}${req.url.slice('/fonts'.length)}`;
        next();
      });
    },
    writeBundle(options) {
      if (options.dir) cpSync(FONTS, path.join(options.dir, 'fonts'), { recursive: true });
    },
  };
}

export default defineConfig({
  root: '.',
  publicDir: 'public', // project.json, audio/, data/ (audio.json, lyrics.json), images
  plugins: [sharedFonts()],
  // OPUS_NO_HMR=1: no live reload (export renders must not reload mid-run when a file changes)
  server: { port: 5173, strictPort: false, hmr: process.env.OPUS_NO_HMR ? false : undefined, fs: { allow: ['.', FONTS] } },
  build: { target: 'esnext', assetsInlineLimit: 0 },
});
