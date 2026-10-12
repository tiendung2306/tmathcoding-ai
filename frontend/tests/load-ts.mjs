import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const modules = new Map();
export async function tsModuleUrl(url) {
  if (modules.has(url.href)) return modules.get(url.href);
  let code = ts.transpileModule(await readFile(url, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const imports = [...code.matchAll(/from (['"])([^'"]+)\1/g)];
  for (const [, quote, specifier] of imports) {
    const resolved = specifier.startsWith('.')
      ? await tsModuleUrl(new URL(`${specifier}.ts`, url))
      : import.meta.resolve(specifier);
    code = code.replace(`${quote}${specifier}${quote}`, JSON.stringify(resolved));
  }
  const compiled = `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
  modules.set(url.href, compiled);
  return compiled;
}
