import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const panelDir = dirname(fileURLToPath(import.meta.url));
const sharedDir = join(panelDir, '..', 'shared');

// Files in frontend/shared have no node_modules of their own, so bare imports
// (e.g. "lit") are resolved from the panel package that owns the dependencies.
function resolveSharedBareImports() {
  return {
    name: 'resolve-shared-bare-imports',
    async resolveId(source, importer, options) {
      if (!importer || !importer.startsWith(sharedDir)) return null;
      if (source.startsWith('.') || source.startsWith('/')) return null;
      return this.resolve(source, join(panelDir, 'index.html'), { ...options, skipSelf: true });
    },
  };
}

export default defineConfig({
  root: panelDir,
  base: './',
  plugins: [resolveSharedBareImports()],
  build: {
    outDir: join(panelDir, '..', '..', 'addon', 'app', 'static', 'panel'),
    emptyOutDir: true,
    target: 'es2022',
    chunkSizeWarningLimit: 1500,
  },
  test: {
    dir: sharedDir,
    include: ['**/*.test.js'],
    environment: 'node',
  },
});
