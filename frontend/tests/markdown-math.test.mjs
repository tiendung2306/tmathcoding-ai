import assert from 'node:assert/strict';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('markdown renderer formats math and keeps code and HTML safe', async () => {
  const vite = await createServer({
    configFile: fileURLToPath(new URL('../vite.config.ts', import.meta.url)),
    server: { middlewareMode: true },
    appType: 'custom',
  });
  try {
    const { MarkdownMath } = await vite.ssrLoadModule('/src/components/MarkdownMath.tsx');
    const html = renderToStaticMarkup(createElement(MarkdownMath, {
      content: [
        '## Ràng buộc',
        '',
        'Inline $N_{max}^2$ and $\\frac{a}{b}$.',
        '',
        '$$',
        'x^2 + y^2 = z^2',
        '$$',
        '',
        'Literal `$N_0$` stays code.',
        '',
        '```text',
        '$N_0$ stays fenced code.',
        '```',
        '',
        '<script>alert(1)</script>',
        '',
        '[reference](https://example.org)',
        '',
        '$\\unknowncommand{x}$',
      ].join('\n'),
    }));

    assert.match(html, /class="katex"/);
    assert.match(html, /class="katex-display"/);
    assert.match(html, /<code>\$N_0\$<\/code>/);
    assert.match(html, /\$N_0\$ stays fenced code\./);
    assert.doesNotMatch(html, /<script>/);
    assert.match(html, /target="_blank" rel="noopener noreferrer"/);
    assert.match(html, /unknowncommand/);
  } finally {
    await vite.close();
  }
});
