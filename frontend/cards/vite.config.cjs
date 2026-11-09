const { createRequire } = require('node:module');
const { join } = require('node:path');

const cardsDir = __dirname;
const panelDir = join(cardsDir, '..', 'panel');
const panelRequire = createRequire(join(panelDir, 'package.json'));
const { defineConfig } = panelRequire('vite');

function resolvePanelDependencies() {
  return {
    name: 'resolve-panel-dependencies',
    async resolveId(source, importer, options) {
      if (!importer || !importer.startsWith(cardsDir)) return null;
      if (source.startsWith('.') || source.startsWith('/')) return null;
      return this.resolve(source, join(panelDir, 'index.html'), { ...options, skipSelf: true });
    },
  };
}

module.exports = defineConfig({
  root: cardsDir,
  base: '',
  plugins: [resolvePanelDependencies()],
  build: {
    lib: {
      entry: join(cardsDir, 'cards.js'),
      formats: ['iife'],
      name: 'MenuPlannerCards',
      fileName: () => 'menu-planner-cards.js',
    },
    outDir: join(cardsDir, '..', '..', 'custom_components', 'menu_planner', 'www'),
    emptyOutDir: true,
    target: 'es2022',
    minify: true,
  },
  test: {
    dir: cardsDir,
    include: ['**/*.test.js'],
    environment: 'node',
  },
});
