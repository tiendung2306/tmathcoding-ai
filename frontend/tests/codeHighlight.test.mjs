import assert from 'node:assert/strict';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

test('submission code uses its language grammar and escapes source HTML', async () => {
  const vite = await createServer({
    configFile: fileURLToPath(new URL('../vite.config.ts', import.meta.url)),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  try {
    const { resolveSourceLanguage, highlightSource } = await vite.ssrLoadModule('/src/lib/codeHighlight.ts');
    assert.equal(resolveSourceLanguage('GNU C++17'), 'cpp');
    assert.equal(resolveSourceLanguage('PyPy 3'), 'python');
    assert.equal(resolveSourceLanguage('JavaScript'), 'javascript');
    assert.equal(resolveSourceLanguage('Java 17'), 'java');
    assert.equal(resolveSourceLanguage('Pascal'), 'delphi');
    assert.equal(resolveSourceLanguage('Go 1.20'), 'go');
    assert.equal(resolveSourceLanguage('unknown'), null);
    assert.match(highlightSource('int main() { return 0; }', 'C++17'), /hljs-/);
    assert.match(highlightSource('def solve():\n    return 1', 'Python 3'), /hljs-/);
    const escaped = highlightSource('<script>alert(1)</script>', 'JavaScript');
    assert.doesNotMatch(escaped, /<script>/);
    assert.equal(highlightSource('plain text', 'unknown'), null);
  } finally {
    await vite.close();
  }
});
